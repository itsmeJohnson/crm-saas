package com.crm.mobile.feature.timeline

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
import retrofit2.http.GET
import retrofit2.http.Query as HttpQuery
import javax.inject.Inject
import javax.inject.Singleton

// ---- Wire DTO (subset of ActivityResponse; Moshi ignores the rest) ----

@JsonClass(generateAdapter = true)
data class ActivityDto(
    val id: String,
    val activity_type: String,
    val subject: String,
    val description: String?,
    val status: String?,
    val call_direction: String?,
    val call_disposition: String?,
    val created_at: String,
)

interface ActivityApi {
    @GET("activities/")
    suspend fun list(@HttpQuery("limit") limit: Int = 100): List<ActivityDto>
}

// ---- Local cache ----

@Entity(tableName = "activities")
data class ActivityEntity(
    @PrimaryKey val id: String,
    val type: String,
    val subject: String,
    val description: String?,
    val direction: String?,
    val disposition: String?,
    val createdAt: String,
)

@Dao
interface ActivityDao {
    @Query("SELECT * FROM activities ORDER BY createdAt DESC")
    fun observeAll(): Flow<List<ActivityEntity>>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertAll(rows: List<ActivityEntity>)

    @Query("DELETE FROM activities")
    suspend fun clear()
}

// ---- Domain ----

data class TimelineActivity(
    val id: String,
    val type: String,
    val subject: String,
    val description: String?,
    val direction: String?,
    val disposition: String?,
    val createdMillis: Long,
) {
    /** Glyph for the timeline row, by channel/type. */
    val glyph: String
        get() = when (type.lowercase()) {
            "call" -> "☎"
            "meeting" -> "◷"
            "sms" -> "✉"
            "whatsapp" -> "❯"
            "email" -> "@"
            "follow-up", "followup" -> "⟳"
            "note" -> "✎"
            else -> "•"
        }
}

private fun ActivityDto.toEntity() =
    ActivityEntity(id, activity_type, subject, description, call_direction, call_disposition, created_at)

private fun ActivityEntity.toDomain(): TimelineActivity? {
    val ms = parseIsoMillis(createdAt) ?: return null
    return TimelineActivity(id, type, subject, description, direction, disposition, ms)
}

/** Offline-first: UI observes the cached feed (newest first); a refresh replaces
 *  it. Type filtering is client-side so every filter works offline. */
@Singleton
class TimelineRepository @Inject constructor(
    private val api: ActivityApi,
    private val dao: ActivityDao,
) {
    val activities: Flow<List<TimelineActivity>> =
        dao.observeAll().map { list -> list.mapNotNull { it.toDomain() } }

    suspend fun refresh(): Boolean = runCatching {
        val fresh = api.list().map { it.toEntity() }
        dao.clear()
        dao.upsertAll(fresh)
        true
    }.getOrDefault(false)
}
