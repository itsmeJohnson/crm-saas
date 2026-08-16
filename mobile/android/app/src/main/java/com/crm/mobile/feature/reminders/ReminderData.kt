package com.crm.mobile.feature.reminders

import androidx.room.Dao
import androidx.room.Entity
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.PrimaryKey
import androidx.room.Query
import com.crm.mobile.feature.tasks.parseIsoMillis
import com.squareup.moshi.JsonClass
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.PATCH
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query as HttpQuery
import java.time.Instant
import java.time.ZoneId
import java.time.ZonedDateTime
import javax.inject.Inject
import javax.inject.Singleton

// ---- Wire DTOs ----
//
// A "reminder" is any Task that carries a `remind_at` timestamp — the backend
// stamps it on follow-up tasks (see follow_up_service) and any manually
// scheduled task. We reuse the existing tasks endpoints (no new backend) and
// filter to those rows client-side, so there is no business logic here.

@JsonClass(generateAdapter = true)
data class ReminderDto(
    val id: String,
    val title: String,
    val description: String?,
    val priority: String,
    val status: String,
    val due_date: String?,
    val remind_at: String?,
    val completed_at: String?,
    val lead_id: String?,
    val updated_at: String?,
)

/** Only the field we change; the backend patches with exclude_unset, so sending
 *  just `remind_at` reschedules the reminder without disturbing anything else. */
@JsonClass(generateAdapter = true)
data class ReminderPatch(val remind_at: String)

interface ReminderApi {
    @GET("tasks/")
    suspend fun list(@HttpQuery("limit") limit: Int = 200): List<ReminderDto>

    @PATCH("tasks/{id}")
    suspend fun patch(@Path("id") id: String, @Body body: ReminderPatch): ReminderDto

    @POST("tasks/{id}/complete")
    suspend fun complete(@Path("id") id: String): ReminderDto
}

// ---- Local cache ----

@Entity(tableName = "reminders")
data class ReminderEntity(
    @PrimaryKey val id: String,
    val title: String,
    val description: String?,
    val priority: String,
    val status: String,
    val dueDate: String?,
    val remindAt: String?,
    val leadId: String?,
    val updatedAt: String?,
)

@Dao
interface ReminderDao {
    @Query("SELECT * FROM reminders ORDER BY remindAt IS NULL, remindAt")
    fun observeAll(): Flow<List<ReminderEntity>>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertAll(rows: List<ReminderEntity>)

    @Query("DELETE FROM reminders")
    suspend fun clear()
}

// ---- Domain ----

enum class ReminderBucket { OVERDUE, TODAY, UPCOMING, COMPLETED }

/** Snooze presets. [nextMillis] is pure so it is unit-testable — the caller
 *  supplies "now" and the zone. */
enum class SnoozeOption(val label: String) {
    ONE_HOUR("In 1 hour"),
    THREE_HOURS("In 3 hours"),
    TOMORROW("Tomorrow 9am"),
    NEXT_WEEK("Next week");

    fun nextMillis(now: Long, zone: ZoneId = ZoneId.systemDefault()): Long = when (this) {
        ONE_HOUR -> now + HOUR_MS
        THREE_HOURS -> now + 3 * HOUR_MS
        TOMORROW -> ZonedDateTime.ofInstant(Instant.ofEpochMilli(now), zone)
            .plusDays(1).withHour(9).withMinute(0).withSecond(0).withNano(0)
            .toInstant().toEpochMilli()
        NEXT_WEEK -> ZonedDateTime.ofInstant(Instant.ofEpochMilli(now), zone)
            .plusWeeks(1).withHour(9).withMinute(0).withSecond(0).withNano(0)
            .toInstant().toEpochMilli()
    }

    private companion object { const val HOUR_MS = 3_600_000L }
}

data class Reminder(
    val id: String,
    val title: String,
    val description: String?,
    val priority: String,
    val status: String,
    val remindAtMillis: Long,
    val dueAtMillis: Long?,
    val leadId: String?,
) {
    val isDone: Boolean get() = status.equals("Done", ignoreCase = true)
}

/** Buckets a reminder against today's [start, end) window (caller supplies the
 *  zone-aware boundaries so this stays pure and unit-testable). Bucketed by
 *  remind_at — the lens that makes this distinct from the Tasks screen. */
fun Reminder.bucket(todayStart: Long, todayEnd: Long): ReminderBucket = when {
    isDone -> ReminderBucket.COMPLETED
    remindAtMillis < todayStart -> ReminderBucket.OVERDUE
    remindAtMillis < todayEnd -> ReminderBucket.TODAY
    else -> ReminderBucket.UPCOMING
}

private fun ReminderDto.toEntity() =
    ReminderEntity(id, title, description, priority, status, due_date, remind_at, lead_id, updated_at)

private fun ReminderEntity.toDomain(): Reminder? {
    val ms = parseIsoMillis(remindAt) ?: return null
    return Reminder(id, title, description, priority, status, ms, parseIsoMillis(dueDate), leadId)
}

/** Offline-first: the UI observes the Room cache; a refresh replaces it with the
 *  reminder-bearing tasks. Snooze/complete round-trip to the API then re-sync. */
@Singleton
class ReminderRepository @Inject constructor(
    private val api: ReminderApi,
    private val dao: ReminderDao,
) {
    val reminders: Flow<List<Reminder>> =
        dao.observeAll().map { list -> list.mapNotNull { it.toDomain() } }

    suspend fun refresh(): Boolean = runCatching {
        val fresh = api.list().filter { !it.remind_at.isNullOrBlank() }.map { it.toEntity() }
        dao.clear()
        dao.upsertAll(fresh)
        true
    }.getOrDefault(false)

    suspend fun snooze(id: String, newRemindAtMillis: Long): Boolean = runCatching {
        api.patch(id, ReminderPatch(remind_at = Instant.ofEpochMilli(newRemindAtMillis).toString()))
        refresh(); true
    }.getOrDefault(false)

    suspend fun complete(id: String): Boolean =
        runCatching { api.complete(id); refresh(); true }.getOrDefault(false)
}
