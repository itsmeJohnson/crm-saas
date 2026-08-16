package com.crm.mobile.feature.reports

import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.IOException

class ReportsRepositoryTest {

    private class FakeDao(var stored: ReportsSnapshotEntity? = null) : ReportsDao {
        override fun observe(): Flow<ReportsSnapshotEntity?> = flow { emit(stored) }
        override suspend fun upsert(row: ReportsSnapshotEntity) { stored = row }
    }

    private class FakeApi : ReportsApi {
        var dash: DashSummaryDto? = DashSummaryDto(total_leads = 10, conversion_rate = 25.0,
            leads_by_status = mapOf("New" to 4, "Won" to 2))
        var task: TaskReportDto? = TaskReportDto(total = 8, open = 5, completed = 3, completion_rate = 37.5,
            by_priority = listOf(LabelCount("High", 3), LabelCount("Low", 5)))
        var comm: CommOverviewDto? = CommOverviewDto(total = 20, outbound = 15, inbound = 5,
            delivery_rate = 90.0, by_channel = listOf(LabelCount("call", 12), LabelCount("sms", 8)))
        var failDash = false; var failTask = false; var failComm = false

        override suspend fun dashboardSummary(): DashSummaryDto =
            if (failDash) throw IOException("offline") else dash!!
        override suspend fun taskReport(): TaskReportDto =
            if (failTask) throw IOException("offline") else task!!
        override suspend fun commOverview(): CommOverviewDto =
            if (failComm) throw IOException("offline") else comm!!
    }

    private fun moshi() = Moshi.Builder().add(KotlinJsonAdapterFactory()).build()

    @Test
    fun refresh_caches_and_parses_all_three_reports() = runTest {
        val repo = ReportsRepository(FakeApi(), FakeDao(), moshi())
        assertTrue(repo.refresh())
        val b = repo.reports.first()!!
        assertEquals(10, b.dashboard?.total_leads)
        assertEquals(25.0, b.dashboard?.conversion_rate!!, 0.001)
        assertEquals(listOf(LabelCount("High", 3), LabelCount("Low", 5)), b.tasks?.by_priority)
        assertEquals(20, b.comm?.total)
        assertEquals(listOf(LabelCount("call", 12), LabelCount("sms", 8)), b.comm?.by_channel)
    }

    @Test
    fun partial_failure_keeps_previous_copy_of_the_failed_report() = runTest {
        val dao = FakeDao()
        val api = FakeApi()
        val repo = ReportsRepository(api, dao, moshi())
        assertTrue(repo.refresh())                       // seed all three

        api.failComm = true                              // comms endpoint now down
        api.dash = DashSummaryDto(total_leads = 99)      // dashboard changed
        assertTrue(repo.refresh())                       // still online (2/3 ok)

        val b = repo.reports.first()!!
        assertEquals(99, b.dashboard?.total_leads)       // updated
        assertNotNull(b.comm)                            // previous comms retained
        assertEquals(20, b.comm?.total)
    }

    @Test
    fun total_failure_returns_false_and_keeps_cache() = runTest {
        val dao = FakeDao()
        val api = FakeApi()
        val repo = ReportsRepository(api, dao, moshi())
        assertTrue(repo.refresh())

        api.failDash = true; api.failTask = true; api.failComm = true
        assertFalse(repo.refresh())                      // all down → offline
        assertEquals(10, repo.reports.first()?.dashboard?.total_leads)  // cache intact
    }

    @Test
    fun empty_cache_maps_to_null_bundle() = runTest {
        val repo = ReportsRepository(FakeApi(), FakeDao(), moshi())
        assertNull(repo.reports.first())
    }
}
