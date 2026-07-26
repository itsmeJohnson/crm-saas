package com.crm.mobile.feature.leads

import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.IOException

/**
 * Pins the offline-first contract of LeadRepository:
 *  - a successful refresh upserts and reports online,
 *  - a network failure keeps the cache and reports offline (never throws),
 *  - the incremental pull passes the newest cached updated_at as the cursor.
 *
 * Uses hand-rolled fakes so it runs as a plain JVM unit test (no device).
 */
class LeadRepositoryTest {

    private class FakeDao(private var stored: MutableList<LeadEntity> = mutableListOf()) : LeadDao {
        var upserted: List<LeadEntity>? = null
        override fun observeAll() = flowOf(stored.toList())
        override suspend fun upsertAll(leads: List<LeadEntity>) { upserted = leads; stored.addAll(leads) }
        override suspend fun latestUpdatedAt() = stored.maxOfOrNull { it.updatedAt ?: "" }?.ifBlank { null }
        override suspend fun clear() { stored.clear() }
    }

    private class FakeApi(
        val result: List<LeadDto> = emptyList(),
        val fail: Boolean = false,
        var seenCursor: String? = null,
    ) : LeadApi {
        override suspend fun list(updatedAfter: String?, limit: Int): List<LeadDto> {
            seenCursor = updatedAfter
            if (fail) throw IOException("offline")
            return result
        }
    }

    @Test
    fun refresh_success_upserts_and_reports_online() = runTest {
        val api = FakeApi(result = listOf(
            LeadDto("1", "Deal A", "Amit", "K", "+91***", "New", 5000.0, "High", null, "2026-07-25T10:00:00Z")
        ))
        val repo = LeadRepository(api, FakeDao())

        val online = repo.refresh()

        assertTrue(online)
        assertEquals("Deal A", repo.leads.first().single().title)
    }

    @Test
    fun refresh_offline_keeps_cache_and_reports_offline() = runTest {
        val cached = mutableListOf(
            LeadEntity("1", "Cached", "Meena", "+91***", "New", 100.0, "Low", "2026-07-20T09:00:00Z")
        )
        val repo = LeadRepository(FakeApi(fail = true), FakeDao(cached))

        val online = repo.refresh()   // must NOT throw

        assertFalse(online)
        assertEquals("Cached", repo.leads.first().single().title)
    }

    @Test
    fun refresh_uses_latest_updated_at_as_incremental_cursor() = runTest {
        val cached = mutableListOf(
            LeadEntity("1", "Old", "A", null, "New", null, "Low", "2026-07-01T00:00:00Z"),
            LeadEntity("2", "Newer", "B", null, "New", null, "Low", "2026-07-24T00:00:00Z"),
        )
        val api = FakeApi()
        LeadRepository(api, FakeDao(cached)).refresh()

        assertEquals("2026-07-24T00:00:00Z", api.seenCursor)
    }
}
