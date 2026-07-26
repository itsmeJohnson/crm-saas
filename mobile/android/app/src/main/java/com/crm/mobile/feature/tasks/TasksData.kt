package com.crm.mobile.feature.tasks

import androidx.room.Dao
import androidx.room.Entity
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.PrimaryKey
import androidx.room.Query
import com.squareup.moshi.JsonClass
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path
import java.time.Instant
import java.time.OffsetDateTime
import javax.inject.Inject
import javax.inject.Singleton

// ---- Wire DTO (subset of TaskResponse) ----

@JsonClass(generateAdapter = true)
data class TaskDto(
    val id: String,
    val title: String,
    val description: String?,
    val priority: String,
    val status: String,
    val due_date: String?,
    val completed_at: String?,
    val lead_id: String?,
    val updated_at: String?,
)

interface TaskApi {
    @GET("tasks/")
    suspend fun list(): List<TaskDto>

    @POST("tasks/{id}/complete")
    suspend fun complete(@Path("id") id: String): TaskDto
}

// ---- Local cache ----

@Entity(tableName = "tasks")
data class TaskEntity(
    @PrimaryKey val id: String,
    val title: String,
    val description: String?,
    val priority: String,
    val status: String,
    val dueDate: String?,
    val leadId: String?,
    val updatedAt: String?,
)

@Dao
interface TaskDao {
    @Query("SELECT * FROM tasks ORDER BY dueDate IS NULL, dueDate")
    fun observeAll(): Flow<List<TaskEntity>>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertAll(tasks: List<TaskEntity>)

    @Query("DELETE FROM tasks")
    suspend fun clear()
}

// ---- Domain ----

enum class TaskBucket { TODAY, UPCOMING, OVERDUE, COMPLETED }

data class Task(
    val id: String,
    val title: String,
    val description: String?,
    val priority: String,
    val status: String,
    val dueAtMillis: Long?,
) {
    val isDone: Boolean get() = status.equals("Done", ignoreCase = true)
}

internal fun parseIsoMillis(s: String?): Long? {
    if (s.isNullOrBlank()) return null
    return runCatching { OffsetDateTime.parse(s).toInstant().toEpochMilli() }
        .recoverCatching { Instant.parse(s).toEpochMilli() }
        .getOrNull()
}

private fun TaskDto.toEntity() =
    TaskEntity(id, title, description, priority, status, due_date, lead_id, updated_at)

private fun TaskEntity.toDomain() =
    Task(id, title, description, priority, status, parseIsoMillis(dueDate))

/** Offline-first: UI observes the Room cache; a refresh replaces it. Bucketing
 *  (today/upcoming/overdue/completed) is derived client-side so all tabs work
 *  offline from one cached list. */
@Singleton
class TaskRepository @Inject constructor(
    private val api: TaskApi,
    private val dao: TaskDao,
) {
    val tasks: Flow<List<Task>> = dao.observeAll().map { list -> list.map { it.toDomain() } }

    suspend fun refresh(): Boolean = runCatching {
        dao.upsertAll(api.list().map { it.toEntity() })
        true
    }.getOrDefault(false)

    suspend fun complete(id: String): Boolean = runCatching { api.complete(id); refresh(); true }.getOrDefault(false)
}

/** Buckets a task against today's [start, end) window (caller supplies the
 *  zone-aware boundaries so this stays pure and unit-testable). */
fun Task.bucket(todayStart: Long, todayEnd: Long): TaskBucket = when {
    isDone -> TaskBucket.COMPLETED
    dueAtMillis == null -> TaskBucket.UPCOMING
    dueAtMillis < todayStart -> TaskBucket.OVERDUE
    dueAtMillis < todayEnd -> TaskBucket.TODAY
    else -> TaskBucket.UPCOMING
}
