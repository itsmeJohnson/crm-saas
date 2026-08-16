package com.crm.mobile.feature.profile

import androidx.room.Dao
import androidx.room.Entity
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.PrimaryKey
import androidx.room.Query
import com.squareup.moshi.JsonClass
import com.squareup.moshi.Moshi
import com.squareup.moshi.Types
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import javax.inject.Inject
import javax.inject.Singleton

// ---- Wire DTOs (subsets; Moshi ignores extra fields) ----

@JsonClass(generateAdapter = true)
data class ProfileMeDto(
    val id: String,
    val email: String,
    val first_name: String?,
    val last_name: String?,
    val role: String,
    val organization_id: String,
)

@JsonClass(generateAdapter = true)
data class AttendanceRecordDto(
    val status: String,
    val clock_in_at: String?,
    val clock_out_at: String?,
    val worked_minutes: Int = 0,
    val break_minutes: Int = 0,
    val is_late: Boolean = false,
)

@JsonClass(generateAdapter = true)
data class AttendanceTodayDto(
    val work_date: String,
    val record: AttendanceRecordDto?,
    val on_break: Boolean = false,
)

@JsonClass(generateAdapter = true)
data class BalanceRowDto(
    val leave_type_name: String,
    val allocated: Double = 0.0,
    val used: Double = 0.0,
    val pending: Double = 0.0,
    val available: Double = 0.0,
)

@JsonClass(generateAdapter = true)
data class ExpenseDto(
    val id: String,
    val category: String,
    val amount: Double = 0.0,
    val description: String?,
    val vendor: String?,
    val incurred_at: String?,
)

/** Empty-but-valid body for clock in/out — the backend's ClockRequest is a
 *  required param whose fields are all optional, so `{}` clocks without GPS. */
@JsonClass(generateAdapter = true)
data class ClockBody(val latitude: Double? = null, val longitude: Double? = null)

interface ProfileApi {
    @GET("auth/me")
    suspend fun me(): ProfileMeDto

    @GET("attendance/me/today")
    suspend fun attendanceToday(): AttendanceTodayDto

    @POST("attendance/clock-in")
    suspend fun clockIn(@Body body: ClockBody): AttendanceRecordDto

    @POST("attendance/clock-out")
    suspend fun clockOut(@Body body: ClockBody): AttendanceRecordDto

    @GET("leaves/balances")
    suspend fun leaveBalances(): List<BalanceRowDto>

    // Manager-only on the backend (_require_manager) — only fetched for managers.
    @GET("financial-analytics/expense-records")
    suspend fun expenses(): List<ExpenseDto>
}

// ---- Local cache: a single snapshot row holding the profile JSON blobs ----

@Entity(tableName = "profile_snapshot")
data class ProfileSnapshotEntity(
    @PrimaryKey val id: String = "me",
    val meJson: String?,
    val attendanceJson: String?,
    val balancesJson: String?,
    val expensesJson: String?,
    val cachedAt: Long,
)

@Dao
interface ProfileDao {
    @Query("SELECT * FROM profile_snapshot WHERE id = 'me'")
    fun observe(): Flow<ProfileSnapshotEntity?>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(row: ProfileSnapshotEntity)
}

// ---- Domain ----

data class ProfileBundle(
    val me: ProfileMeDto?,
    val attendance: AttendanceTodayDto?,
    val balances: List<BalanceRowDto>,
    val expenses: List<ExpenseDto>,
    val cachedAt: Long,
) {
    val isClockedIn: Boolean
        get() {
            val r = attendance?.record ?: return false
            return r.clock_in_at != null && r.clock_out_at == null
        }
}

/**
 * Offline-first: the UI observes the cached snapshot. A refresh fetches me /
 * attendance / balances always and expenses only for managers, each
 * independently — a partial failure keeps the previous copy of whatever didn't
 * load. Returns false only when everything attempted fails (treated as offline).
 */
@Singleton
class ProfileRepository @Inject constructor(
    private val api: ProfileApi,
    private val dao: ProfileDao,
    moshi: Moshi,
) {
    private val meAdapter = moshi.adapter(ProfileMeDto::class.java)
    private val attAdapter = moshi.adapter(AttendanceTodayDto::class.java)
    private val balAdapter =
        moshi.adapter<List<BalanceRowDto>>(Types.newParameterizedType(List::class.java, BalanceRowDto::class.java))
    private val expAdapter =
        moshi.adapter<List<ExpenseDto>>(Types.newParameterizedType(List::class.java, ExpenseDto::class.java))

    val profile: Flow<ProfileBundle?> = dao.observe().map { row -> row?.let { toDomain(it) } }

    suspend fun refresh(includeExpenses: Boolean): Boolean {
        val prev = dao.observe().first()
        val me = runCatching { api.me() }.getOrNull()
        val att = runCatching { api.attendanceToday() }.getOrNull()
        val bal = runCatching { api.leaveBalances() }.getOrNull()
        val exp = if (includeExpenses) runCatching { api.expenses() }.getOrNull() else null

        val gotSomething = me != null || att != null || bal != null || (includeExpenses && exp != null)
        if (!gotSomething) return false

        dao.upsert(
            ProfileSnapshotEntity(
                meJson = me?.let { meAdapter.toJson(it) } ?: prev?.meJson,
                attendanceJson = att?.let { attAdapter.toJson(it) } ?: prev?.attendanceJson,
                balancesJson = bal?.let { balAdapter.toJson(it) } ?: prev?.balancesJson,
                // When we didn't fetch expenses this time, keep whatever we had.
                expensesJson = exp?.let { expAdapter.toJson(it) } ?: prev?.expensesJson,
                cachedAt = System.currentTimeMillis(),
            ),
        )
        return true
    }

    suspend fun clockIn(includeExpenses: Boolean): Boolean =
        runCatching { api.clockIn(ClockBody()); refresh(includeExpenses); true }.getOrDefault(false)

    suspend fun clockOut(includeExpenses: Boolean): Boolean =
        runCatching { api.clockOut(ClockBody()); refresh(includeExpenses); true }.getOrDefault(false)

    private fun toDomain(row: ProfileSnapshotEntity) = ProfileBundle(
        me = row.meJson?.let { runCatching { meAdapter.fromJson(it) }.getOrNull() },
        attendance = row.attendanceJson?.let { runCatching { attAdapter.fromJson(it) }.getOrNull() },
        balances = row.balancesJson?.let { runCatching { balAdapter.fromJson(it) }.getOrNull() }.orEmpty(),
        expenses = row.expensesJson?.let { runCatching { expAdapter.fromJson(it) }.getOrNull() }.orEmpty(),
        cachedAt = row.cachedAt,
    )
}
