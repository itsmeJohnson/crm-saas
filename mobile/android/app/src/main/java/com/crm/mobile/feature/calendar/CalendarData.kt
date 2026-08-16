package com.crm.mobile.feature.calendar

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

// ---- Wire DTO (subset of CalendarItem; Moshi ignores the rest) ----

@JsonClass(generateAdapter = true)
data class CalendarItemDto(
    val id: String,
    val source: String,      // event|task|activity|followup|holiday
    val type: String,
    val title: String,
    val start: String,
    val end: String?,
    val all_day: Boolean = false,
    val status: String?,
)

interface CalendarApi {
    // date_from/date_to are required ISO datetimes on the backend.
    @GET("calendar/")
    suspend fun unified(
        @HttpQuery("date_from") from: String,
        @HttpQuery("date_to") to: String,
    ): List<CalendarItemDto>
}

// ---- Local cache (holds the last-fetched window for offline viewing) ----

@Entity(tableName = "calendar_items")
data class CalendarItemEntity(
    @PrimaryKey val id: String,
    val source: String,
    val type: String,
    val title: String,
    val start: String,
    val end: String?,
    val allDay: Boolean,
    val status: String?,
)

@Dao
interface CalendarDao {
    @Query("SELECT * FROM calendar_items ORDER BY start")
    fun observeAll(): Flow<List<CalendarItemEntity>>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertAll(items: List<CalendarItemEntity>)

    @Query("DELETE FROM calendar_items")
    suspend fun clear()
}

// ---- Domain ----

data class CalItem(
    val id: String,
    val source: String,
    val type: String,
    val title: String,
    val startMillis: Long,
    val endMillis: Long?,
    val allDay: Boolean,
    val status: String?,
) {
    // Tasks and follow-ups always schedule a reminder in this CRM.
    val hasReminder: Boolean get() = source == "task" || source == "followup"
}

private fun CalendarItemDto.toEntity() =
    CalendarItemEntity(id, source, type, title, start, end, all_day, status)

private fun CalendarItemEntity.toDomain(): CalItem? {
    val startMs = parseIsoMillis(start) ?: return null
    return CalItem(id, source, type, title, startMs, parseIsoMillis(end), allDay, status)
}

/** Offline-first: the UI observes the cached window; a refresh replaces it with
 *  the requested date range. A failed refresh keeps the last window visible. */
@Singleton
class CalendarRepository @Inject constructor(
    private val api: CalendarApi,
    private val dao: CalendarDao,
) {
    val items: Flow<List<CalItem>> = dao.observeAll().map { list -> list.mapNotNull { it.toDomain() } }

    suspend fun refresh(fromIso: String, toIso: String): Boolean = runCatching {
        val fresh = api.unified(fromIso, toIso).map { it.toEntity() }
        dao.clear()
        dao.upsertAll(fresh)
        true
    }.getOrDefault(false)
}
