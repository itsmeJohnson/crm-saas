package com.crm.mobile.feature.timeline

import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.IOException

class TimelineRepositoryTest {

    private class FakeDao(private val stored: MutableList<ActivityEntity> = mutableListOf()) : ActivityDao {
        override fun observeAll(): Flow<List<ActivityEntity>> = flow { emit(stored.toList()) }
        override suspend fun upsertAll(rows: List<ActivityEntity>) { stored.addAll(rows) }
        override suspend fun clear() { stored.clear() }
    }

    private class FakeApi(val result: List<ActivityDto> = emptyList(), val fail: Boolean = false) : ActivityApi {
        override suspend fun list(limit: Int): List<ActivityDto> { if (fail) throw IOException("offline"); return result }
    }

    @Test
    fun refresh_caches_and_maps_glyph() = runTest {
        val api = FakeApi(listOf(
            ActivityDto("a1", "Call", "Called Amit", "Picked up", "Completed", "OUTBOUND", "Picked", "2026-07-26T09:00:00Z"),
            ActivityDto("a2", "WhatsApp", "Sent quote", null, "sent", null, null, "2026-07-26T10:00:00Z"),
        ))
        val repo = TimelineRepository(api, FakeDao())
        assertTrue(repo.refresh())
        val items = repo.activities.first()
        assertEquals(2, items.size)
        assertEquals("☎", items.first { it.id == "a1" }.glyph)
        assertEquals("❯", items.first { it.id == "a2" }.glyph)
    }

    @Test
    fun bad_timestamp_is_dropped() = runTest {
        val dao = FakeDao(mutableListOf(
            ActivityEntity("ok", "Call", "Good", null, null, null, "2026-07-26T09:00:00Z"),
            ActivityEntity("bad", "Call", "Broken", null, null, null, "not-a-date"),
        ))
        val repo = TimelineRepository(FakeApi(), dao)
        assertEquals(listOf("ok"), repo.activities.first().map { it.id })
    }

    @Test
    fun refresh_offline_keeps_cache() = runTest {
        val cached = mutableListOf(ActivityEntity("c1", "Email", "Cached", null, null, null, "2026-07-20T09:00:00Z"))
        val repo = TimelineRepository(FakeApi(fail = true), FakeDao(cached))
        assertFalse(repo.refresh())
        assertEquals("Cached", repo.activities.first().single().subject)
    }
}
