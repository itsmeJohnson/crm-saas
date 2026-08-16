package com.crm.mobile.feature.dashboard

import android.util.Log
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
import kotlinx.coroutines.flow.map
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Query as HttpQuery
import javax.inject.Inject
import javax.inject.Singleton

// ---- Wire DTOs (subset of /dashboard/employee + /dashboard/recent-activities) ----

@JsonClass(generateAdapter = true)
data class EmployeeSummaryDto(
    val employee_name: String?,
    val is_online: Boolean = false,
    val check_in_at: String?,
    val check_out_at: String?,
    val working_minutes: Int = 0,
    val calls_made_today: Int = 0,
    val todays_follow_ups: Int = 0,
    val overdue_follow_ups: Int = 0,
    val interested_leads: Int = 0,
    val new_leads: Int = 0,
    val meetings_today: Int = 0,
    val tasks_pending: Int = 0,
    val overdue_tasks: Int = 0,
    val my_leads_total: Int = 0,
    val my_leads_converted: Int = 0,
)

@JsonClass(generateAdapter = true)
data class RecentActivityDto(
    val id: String,
    val activity_type: String?,
    val subject: String?,
    val status: String?,
    val created_at: String,
)

@JsonClass(generateAdapter = true)
data class RecentActivitiesDto(val items: List<RecentActivityDto> = emptyList())

@JsonClass(generateAdapter = true)
data class ClockBody(val latitude: Double? = null, val longitude: Double? = null)

interface DashboardApi {
    @GET("dashboard/employee")
    suspend fun employeeSummary(): EmployeeSummaryDto

    @GET("dashboard/recent-activities")
    suspend fun recentActivities(@HttpQuery("limit") limit: Int = 15): RecentActivitiesDto

    @POST("attendance/clock-in")
    suspend fun clockIn(@Body body: ClockBody = ClockBody()): Unit

    @POST("attendance/clock-out")
    suspend fun clockOut(@Body body: ClockBody = ClockBody()): Unit
}

// ---- Local cache: a single snapshot row so the dashboard renders offline ----

@Entity(tableName = "dashboard_snapshot")
data class DashboardSnapshotEntity(
    @PrimaryKey val id: String = "me",
    val employeeName: String?,
    val isOnline: Boolean,
    val checkInAt: String?,
    val checkOutAt: String?,
    val workingMinutes: Int,
    val callsToday: Int,
    val todaysFollowUps: Int,
    val overdueFollowUps: Int,
    val interestedLeads: Int,
    val meetingsToday: Int,
    val tasksPending: Int,
    val overdueTasks: Int,
    val leadsTotal: Int,
    val leadsConverted: Int,
    val recentActivitiesJson: String?,
    val cachedAt: Long,
)

@Dao
interface DashboardDao {
    @Query("SELECT * FROM dashboard_snapshot WHERE id = 'me'")
    fun observe(): Flow<DashboardSnapshotEntity?>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(snapshot: DashboardSnapshotEntity)
}

// ---- Domain ----

data class RecentActivity(val id: String, val type: String, val subject: String, val status: String?)

data class DashboardSummary(
    val employeeName: String,
    val isOnline: Boolean,
    val checkInAt: String?,
    val workingMinutes: Int,
    val callsToday: Int,
    val todaysFollowUps: Int,
    val overdueFollowUps: Int,
    val interestedLeads: Int,
    val meetingsToday: Int,
    val tasksPending: Int,
    val overdueTasks: Int,
    val leadsTotal: Int,
    val leadsConverted: Int,
    val recent: List<RecentActivity>,
) {
    /** Conversion progress (converted / total) used as the target-progress bar
     *  until the /targets API is wired in a later module. */
    val conversionProgress: Float
        get() = if (leadsTotal > 0) leadsConverted.toFloat() / leadsTotal else 0f
}

/**
 * Offline-first: the UI observes the cached snapshot (renders instantly, works
 * offline); a refresh pulls /dashboard/employee + recent activities and upserts.
 * A network failure leaves the last snapshot intact.
 */
@Singleton
class DashboardRepository @Inject constructor(
    private val api: DashboardApi,
    private val dao: DashboardDao,
    private val moshi: Moshi,
) {
    private val activitiesAdapter =
        moshi.adapter<List<RecentActivityDto>>(Types.newParameterizedType(List::class.java, RecentActivityDto::class.java))

    val summary: Flow<DashboardSummary?> = dao.observe().map { it?.toDomain(activitiesAdapter) }

    /** True on a successful refresh, false if offline (cached snapshot kept). */
    suspend fun refresh(): Boolean = runCatching {
        val s = api.employeeSummary()
        val recent = runCatching { api.recentActivities().items }.getOrDefault(emptyList())
        dao.upsert(s.toEntity(recent, activitiesAdapter))
        true
    }.getOrDefault(false)

    suspend fun clockIn(): Boolean = runCatching { api.clockIn(); refresh(); true }.getOrDefault(false)
    suspend fun clockOut(): Boolean = runCatching { api.clockOut(); refresh(); true }.getOrDefault(false)
}

private fun EmployeeSummaryDto.toEntity(
    recent: List<RecentActivityDto>,
    adapter: com.squareup.moshi.JsonAdapter<List<RecentActivityDto>>,
) = DashboardSnapshotEntity(
    employeeName = employee_name,
    isOnline = is_online,
    checkInAt = check_in_at,
    checkOutAt = check_out_at,
    workingMinutes = working_minutes,
    callsToday = calls_made_today,
    todaysFollowUps = todays_follow_ups,
    overdueFollowUps = overdue_follow_ups,
    interestedLeads = interested_leads,
    meetingsToday = meetings_today,
    tasksPending = tasks_pending,
    overdueTasks = overdue_tasks,
    leadsTotal = my_leads_total,
    leadsConverted = my_leads_converted,
    recentActivitiesJson = adapter.toJson(recent),
    cachedAt = System.currentTimeMillis(),
)

private fun DashboardSnapshotEntity.toDomain(
    adapter: com.squareup.moshi.JsonAdapter<List<RecentActivityDto>>,
): DashboardSummary {
    val recent = recentActivitiesJson?.let { runCatching { adapter.fromJson(it) }.getOrNull() }.orEmpty()
    return DashboardSummary(
        employeeName = employeeName ?: "—",
        isOnline = isOnline,
        checkInAt = checkInAt,
        workingMinutes = workingMinutes,
        callsToday = callsToday,
        todaysFollowUps = todaysFollowUps,
        overdueFollowUps = overdueFollowUps,
        interestedLeads = interestedLeads,
        meetingsToday = meetingsToday,
        tasksPending = tasksPending,
        overdueTasks = overdueTasks,
        leadsTotal = leadsTotal,
        leadsConverted = leadsConverted,
        recent = recent.map { RecentActivity(it.id, it.activity_type ?: "Activity", it.subject ?: "—", it.status) },
    )
}
