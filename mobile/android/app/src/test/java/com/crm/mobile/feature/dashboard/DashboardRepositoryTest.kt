package com.crm.mobile.feature.dashboard

import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.IOException

/** Pins Module 1's offline-first contract: a good refresh caches the snapshot;
 *  a network failure keeps the last snapshot and reports offline (never throws). */
class DashboardRepositoryTest {

    private val moshi = Moshi.Builder().add(KotlinJsonAdapterFactory()).build()

    private class FakeDao(var stored: DashboardSnapshotEntity? = null) : DashboardDao {
        override fun observe(): Flow<DashboardSnapshotEntity?> = flow { emit(stored) }
        override suspend fun upsert(snapshot: DashboardSnapshotEntity) { stored = snapshot }
    }

    private class FakeApi(
        val summary: EmployeeSummaryDto? = null,
        val fail: Boolean = false,
    ) : DashboardApi {
        override suspend fun employeeSummary(): EmployeeSummaryDto {
            if (fail) throw IOException("offline")
            return summary!!
        }
        override suspend fun recentActivities(limit: Int) =
            RecentActivitiesDto(listOf(RecentActivityDto("a1", "Call", "Called Amit", "Completed", "2026-07-26T09:00:00Z")))
        override suspend fun clockIn(body: ClockBody) = Unit
        override suspend fun clockOut(body: ClockBody) = Unit
    }

    @Test
    fun refresh_success_caches_snapshot_and_maps_metrics() = runTest {
        val api = FakeApi(summary = EmployeeSummaryDto(
            employee_name = "Meena Joshi", is_online = true, check_in_at = "2026-07-26T09:00:00Z",
            check_out_at = null, working_minutes = 125, calls_made_today = 12,
            todays_follow_ups = 5, overdue_follow_ups = 2, interested_leads = 7, new_leads = 3,
            meetings_today = 1, tasks_pending = 4, overdue_tasks = 1,
            my_leads_total = 40, my_leads_converted = 10,
        ))
        val repo = DashboardRepository(api, FakeDao(), moshi)

        val online = repo.refresh()
        assertTrue(online)

        val s = repo.summary.first()
        assertNotNull(s)
        assertEquals("Meena Joshi", s!!.employeeName)
        assertEquals(12, s.callsToday)
        assertEquals(2, s.overdueFollowUps)
        assertEquals(0.25f, s.conversionProgress)          // 10 / 40
        assertEquals("Called Amit", s.recent.single().subject)
    }

    @Test
    fun refresh_offline_keeps_cached_snapshot() = runTest {
        val cached = DashboardSnapshotEntity(
            employeeName = "Cached User", isOnline = false, checkInAt = null, checkOutAt = null,
            workingMinutes = 0, callsToday = 3, todaysFollowUps = 0, overdueFollowUps = 0,
            interestedLeads = 0, meetingsToday = 0, tasksPending = 0, overdueTasks = 0,
            leadsTotal = 0, leadsConverted = 0, recentActivitiesJson = null, cachedAt = 1L,
        )
        val repo = DashboardRepository(FakeApi(fail = true), FakeDao(cached), moshi)

        val online = repo.refresh()   // must NOT throw
        assertFalse(online)

        assertEquals("Cached User", repo.summary.first()!!.employeeName)
    }
}
