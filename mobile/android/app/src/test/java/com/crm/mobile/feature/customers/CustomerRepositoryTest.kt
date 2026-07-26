package com.crm.mobile.feature.customers

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

class CustomerRepositoryTest {

    private class FakeDao(private val stored: MutableList<CustomerEntity> = mutableListOf()) : CustomerDao {
        override fun observeAll(): Flow<List<CustomerEntity>> = flow { emit(stored.toList()) }
        override suspend fun byId(id: String) = stored.find { it.companyId == id }
        override suspend fun upsertAll(rows: List<CustomerEntity>) { stored.addAll(rows) }
        override suspend fun clear() { stored.clear() }
    }

    private class FakeApi(
        val listResult: List<CustomerListItemDto> = emptyList(),
        val timelineResult: List<TimelineEventDto> = emptyList(),
        val fail: Boolean = false,
    ) : CustomerApi {
        override suspend fun list(): List<CustomerListItemDto> { if (fail) throw IOException("offline"); return listResult }
        override suspend fun timeline(companyId: String): List<TimelineEventDto> {
            if (fail) throw IOException("offline"); return timelineResult
        }
    }

    @Test
    fun refresh_success_caches() = runTest {
        val api = FakeApi(listResult = listOf(CustomerListItemDto("c1", "Acme", "Real Estate", 3, 500000.0, 120000.0)))
        val repo = CustomerRepository(api, FakeDao())
        assertTrue(repo.refresh())
        val c = repo.customers.first().single()
        assertEquals("Acme", c.name)
        assertEquals(120000.0, c.outstandingBalance, 0.001)
    }

    @Test
    fun refresh_offline_keeps_cache() = runTest {
        val cached = mutableListOf(CustomerEntity("c1", "Cached Co", null, 0, 0.0, 0.0))
        val repo = CustomerRepository(FakeApi(fail = true), FakeDao(cached))
        assertFalse(repo.refresh())
        assertEquals("Cached Co", repo.customers.first().single().name)
    }

    @Test
    fun timeline_success_and_failure_are_result_wrapped() = runTest {
        val ok = CustomerRepository(
            FakeApi(timelineResult = listOf(
                TimelineEventDto("t1", "call", "Communication", "Called", null, "Meena", "activity", "2026-07-26T09:00:00Z"))),
            FakeDao())
        val r = ok.timeline("c1")
        assertTrue(r.isSuccess)
        assertEquals("Called", r.getOrThrow().single().title)

        val offline = CustomerRepository(FakeApi(fail = true), FakeDao())
        assertTrue(offline.timeline("c1").isFailure)
    }

    @Test
    fun customer_lookup_reads_cache() = runTest {
        val repo = CustomerRepository(FakeApi(), FakeDao(mutableListOf(
            CustomerEntity("c9", "Nine", null, 1, 10.0, 2.0))))
        assertEquals("Nine", repo.customer("c9")?.name)
        assertNull(repo.customer("nope"))
    }
}
