package com.crm.mobile.feature.notifications

import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.IOException

class NotificationRepositoryTest {

    private class FakeDao(private val stored: MutableList<NotificationEntity> = mutableListOf()) : NotificationDao {
        override fun observeAll(): Flow<List<NotificationEntity>> = flow { emit(stored.toList()) }
        override suspend fun upsertAll(rows: List<NotificationEntity>) { stored.addAll(rows) }
        override suspend fun markReadLocal(id: String) {
            stored.replaceAll { if (it.id == id) it.copy(isRead = true) else it }
        }
        override suspend fun markAllReadLocal() { stored.replaceAll { it.copy(isRead = true) } }
        override suspend fun deleteLocal(id: String) { stored.removeAll { it.id == id } }
        override suspend fun clear() { stored.clear() }
    }

    private class FakeApi(
        var rows: List<NotificationDto> = emptyList(),
        val failList: Boolean = false,
    ) : NotificationApi {
        var readId: String? = null
        var markedAll = false
        var dismissedId: String? = null

        override suspend fun list(limit: Int, includeDismissed: Boolean): List<NotificationDto> {
            if (failList) throw IOException("offline"); return rows
        }
        override suspend fun unreadCount() = UnreadCountDto(rows.count { !it.is_read })
        override suspend fun markRead(id: String): NotificationDto {
            readId = id; return rows.first { it.id == id }.copy(is_read = true)
        }
        override suspend fun markAllRead(): MarkAllResult {
            markedAll = true; return MarkAllResult(rows.count { !it.is_read })
        }
        override suspend fun dismiss(id: String): NotificationDto {
            dismissedId = id; return rows.first { it.id == id }.copy(is_dismissed = true)
        }
    }

    private fun dto(id: String, read: Boolean, link: String? = null, priority: String = "normal") =
        NotificationDto(id, "reminder", "Title $id", "Body $id", link, read, priority, false, "2026-07-26T09:00:00Z")

    @Test
    fun refresh_caches_and_derives_unread_count() = runTest {
        val api = FakeApi(listOf(dto("n1", read = false), dto("n2", read = true), dto("n3", read = false)))
        val repo = NotificationRepository(api, FakeDao())
        assertTrue(repo.refresh())
        assertEquals(3, repo.notifications.first().size)
        assertEquals(2, repo.unreadCount.first())
    }

    @Test
    fun refresh_offline_keeps_cache() = runTest {
        val cached = mutableListOf(
            NotificationEntity("c1", "reminder", "Cached", "b", null, false, "normal", "2026-07-20T09:00:00Z"),
        )
        val repo = NotificationRepository(FakeApi(failList = true), FakeDao(cached))
        assertFalse(repo.refresh())
        assertEquals("Cached", repo.notifications.first().single().title)
        assertEquals(1, repo.unreadCount.first())
    }

    @Test
    fun mark_read_is_optimistic_and_calls_api() = runTest {
        val dao = FakeDao(mutableListOf(
            NotificationEntity("n1", "reminder", "T", "b", null, false, "normal", "2026-07-26T09:00:00Z"),
        ))
        val api = FakeApi(listOf(dto("n1", read = false)))
        val repo = NotificationRepository(api, dao)
        assertTrue(repo.markRead("n1"))
        assertEquals("n1", api.readId)
        assertEquals(0, repo.unreadCount.first())     // reflected locally before any refresh
    }

    @Test
    fun mark_all_read_clears_unread_locally() = runTest {
        val dao = FakeDao(mutableListOf(
            NotificationEntity("n1", "reminder", "T", "b", null, false, "normal", "2026-07-26T09:00:00Z"),
            NotificationEntity("n2", "system", "U", "b", null, false, "high", "2026-07-26T10:00:00Z"),
        ))
        val repo = NotificationRepository(FakeApi(), dao)
        assertTrue(repo.markAllRead())
        assertEquals(0, repo.unreadCount.first())
    }

    @Test
    fun dismiss_removes_from_cache_immediately() = runTest {
        val dao = FakeDao(mutableListOf(
            NotificationEntity("n1", "reminder", "Keep", "b", null, false, "normal", "2026-07-26T09:00:00Z"),
            NotificationEntity("n2", "reminder", "Drop", "b", null, false, "normal", "2026-07-26T10:00:00Z"),
        ))
        val api = FakeApi(listOf(dto("n1", read = false), dto("n2", read = false)))
        val repo = NotificationRepository(api, dao)
        assertTrue(repo.dismiss("n2"))
        assertEquals("n2", api.dismissedId)
        assertEquals(listOf("n1"), repo.notifications.first().map { it.id })
    }

    @Test
    fun deep_link_maps_known_paths_and_ignores_others() {
        assertEquals("leads", deepLinkToRoute("/leads/123"))
        assertEquals("tasks", deepLinkToRoute("https://app/tasks/9"))
        assertEquals("reminders", deepLinkToRoute("/reminders"))
        assertEquals("customers", deepLinkToRoute("/customers/7"))
        assertEquals("calendar", deepLinkToRoute("/calendar/event/3"))
        assertNull(deepLinkToRoute("/settings/profile"))
        assertNull(deepLinkToRoute(null))
        assertNull(deepLinkToRoute(""))
    }

    @Test
    fun moshi_parses_notification_response_ignoring_extra_fields() {
        val moshi = Moshi.Builder().add(KotlinJsonAdapterFactory()).build()
        val json = """
            {"id":"n1","category":"reminder","title":"Follow up Amit","body":"Due now",
             "link_url":"/leads/9","is_read":false,"read_at":null,"action_metadata":{"x":1},
             "priority":"high","is_dismissed":false,"actions":[{"label":"Open"}],
             "channels_sent":["in_app"],"created_at":"2026-07-26T09:00:00Z"}
        """.trimIndent()
        val dto = moshi.adapter(NotificationDto::class.java).fromJson(json)!!
        assertEquals("n1", dto.id)
        assertEquals("/leads/9", dto.link_url)
        assertFalse(dto.is_read)
        assertEquals("high", dto.priority)
    }
}
