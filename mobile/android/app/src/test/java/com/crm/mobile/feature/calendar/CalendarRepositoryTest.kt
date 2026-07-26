package com.crm.mobile.feature.calendar

import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.IOException

class CalendarRepositoryTest {

    private class FakeDao(private val stored: MutableList<CalendarItemEntity> = mutableListOf()) : CalendarDao {
        override fun observeAll(): Flow<List<CalendarItemEntity>> = flow { emit(stored.toList()) }
        override suspend fun upsertAll(items: List<CalendarItemEntity>) { stored.addAll(items) }
        override suspend fun clear() { stored.clear() }
    }

    private class FakeApi(val result: List<CalendarItemDto> = emptyList(), val fail: Boolean = false) : CalendarApi {
        override suspend fun unified(from: String, to: String): List<CalendarItemDto> {
            if (fail) throw IOException("offline"); return result
        }
    }

    @Test
    fun refresh_success_caches_and_maps_reminder_flag() = runTest {
        val api = FakeApi(listOf(
            CalendarItemDto("e1", "event", "Meeting", "Kickoff", "2026-07-26T10:00:00Z", null, false, "Scheduled"),
            CalendarItemDto("f1", "followup", "Follow-up", "Call Amit", "2026-07-26T14:00:00Z", null, false, null),
        ))
        val repo = CalendarRepository(api, FakeDao())
        assertTrue(repo.refresh("a", "b"))

        val items = repo.items.first()
        assertEquals(2, items.size)
        assertFalse(items.first { it.id == "e1" }.hasReminder)  // event → no reminder badge
        assertTrue(items.first { it.id == "f1" }.hasReminder)   // follow-up → reminder badge
    }

    @Test
    fun items_with_unparseable_start_are_dropped() = runTest {
        val dao = FakeDao(mutableListOf(
            CalendarItemEntity("ok", "event", "Meeting", "Good", "2026-07-26T10:00:00Z", null, false, null),
            CalendarItemEntity("bad", "event", "Meeting", "Broken", "not-a-date", null, false, null),
        ))
        val repo = CalendarRepository(FakeApi(), dao)
        val items = repo.items.first()
        assertEquals(listOf("ok"), items.map { it.id })
    }

    @Test
    fun refresh_offline_keeps_cache() = runTest {
        val cached = mutableListOf(
            CalendarItemEntity("c1", "event", "Meeting", "Cached", "2026-07-20T09:00:00Z", null, false, null))
        val repo = CalendarRepository(FakeApi(fail = true), FakeDao(cached))
        assertFalse(repo.refresh("a", "b"))
        assertEquals("Cached", repo.items.first().single().title)
    }
}
