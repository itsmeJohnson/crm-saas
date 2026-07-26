package com.crm.mobile.feature.notifications

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
import retrofit2.http.PATCH
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query as HttpQuery
import javax.inject.Inject
import javax.inject.Singleton

// ---- Wire DTOs (subset of NotificationResponse; Moshi ignores the rest) ----

@JsonClass(generateAdapter = true)
data class NotificationDto(
    val id: String,
    val category: String,
    val title: String,
    val body: String,
    val link_url: String?,
    val is_read: Boolean,
    val priority: String = "normal",
    val is_dismissed: Boolean = false,
    val created_at: String,
)

@JsonClass(generateAdapter = true)
data class UnreadCountDto(val unread_count: Int)

@JsonClass(generateAdapter = true)
data class MarkAllResult(val marked_read: Int)

interface NotificationApi {
    @GET("notifications/")
    suspend fun list(
        @HttpQuery("limit") limit: Int = 50,
        @HttpQuery("include_dismissed") includeDismissed: Boolean = false,
    ): List<NotificationDto>

    @GET("notifications/unread-count")
    suspend fun unreadCount(): UnreadCountDto

    @PATCH("notifications/{id}/read")
    suspend fun markRead(@Path("id") id: String): NotificationDto

    @POST("notifications/mark-all-read")
    suspend fun markAllRead(): MarkAllResult

    @POST("notifications/{id}/dismiss")
    suspend fun dismiss(@Path("id") id: String): NotificationDto
}

// ---- Local cache ----

@Entity(tableName = "notifications")
data class NotificationEntity(
    @PrimaryKey val id: String,
    val category: String,
    val title: String,
    val body: String,
    val linkUrl: String?,
    val isRead: Boolean,
    val priority: String,
    val createdAt: String,
)

@Dao
interface NotificationDao {
    @Query("SELECT * FROM notifications ORDER BY createdAt DESC")
    fun observeAll(): Flow<List<NotificationEntity>>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertAll(rows: List<NotificationEntity>)

    @Query("UPDATE notifications SET isRead = 1 WHERE id = :id")
    suspend fun markReadLocal(id: String)

    @Query("UPDATE notifications SET isRead = 1")
    suspend fun markAllReadLocal()

    @Query("DELETE FROM notifications WHERE id = :id")
    suspend fun deleteLocal(id: String)

    @Query("DELETE FROM notifications")
    suspend fun clear()
}

// ---- Domain ----

data class AppNotification(
    val id: String,
    val category: String,
    val title: String,
    val body: String,
    val linkUrl: String?,
    val isRead: Boolean,
    val priority: String,
    val createdMillis: Long,
) {
    val isHigh: Boolean get() = priority.equals("high", ignoreCase = true) ||
        priority.equals("urgent", ignoreCase = true)
}

/** Maps a backend link_url (e.g. "/leads/123", "/tasks/9") to an in-app route
 *  name, or null if we don't host that destination natively yet. Route literals
 *  intentionally mirror [com.crm.mobile.app.Routes]. Pure + unit-testable. */
fun deepLinkToRoute(url: String?): String? {
    if (url.isNullOrBlank()) return null
    val u = url.lowercase()
    return when {
        "lead" in u -> "leads"
        "task" in u -> "tasks"
        "reminder" in u -> "reminders"
        "customer" in u -> "customers"
        "contact" in u -> "contacts"
        "calendar" in u || "event" in u -> "calendar"
        else -> null
    }
}

private fun NotificationDto.toEntity() =
    NotificationEntity(id, category, title, body, link_url, is_read, priority, created_at)

private fun NotificationEntity.toDomain(): AppNotification? {
    val ms = parseIsoMillis(createdAt) ?: return null
    return AppNotification(id, category, title, body, linkUrl, isRead, priority, ms)
}

/** Offline-first: the UI observes the Room cache (newest first) and the derived
 *  unread count. Mark-read / mark-all / dismiss apply optimistically to the
 *  cache, then round-trip to the API. A refresh replaces the cache — because we
 *  never fetch dismissed rows, dismissed notifications drop out on next sync. */
@Singleton
class NotificationRepository @Inject constructor(
    private val api: NotificationApi,
    private val dao: NotificationDao,
) {
    val notifications: Flow<List<AppNotification>> =
        dao.observeAll().map { list -> list.mapNotNull { it.toDomain() } }

    val unreadCount: Flow<Int> =
        dao.observeAll().map { list -> list.count { !it.isRead } }

    suspend fun refresh(): Boolean = runCatching {
        val fresh = api.list().map { it.toEntity() }
        dao.clear()
        dao.upsertAll(fresh)
        true
    }.getOrDefault(false)

    suspend fun markRead(id: String): Boolean = runCatching {
        dao.markReadLocal(id)
        api.markRead(id); true
    }.getOrDefault(false)

    suspend fun markAllRead(): Boolean = runCatching {
        dao.markAllReadLocal()
        api.markAllRead(); true
    }.getOrDefault(false)

    suspend fun dismiss(id: String): Boolean = runCatching {
        dao.deleteLocal(id)
        api.dismiss(id); true
    }.getOrDefault(false)
}
