package com.crm.mobile.feature.profile

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

class ProfileRepositoryTest {

    private class FakeDao(var stored: ProfileSnapshotEntity? = null) : ProfileDao {
        override fun observe(): Flow<ProfileSnapshotEntity?> = flow { emit(stored) }
        override suspend fun upsert(row: ProfileSnapshotEntity) { stored = row }
    }

    private class FakeApi : ProfileApi {
        var me: ProfileMeDto? = ProfileMeDto("u1", "a@b.com", "Amit", "Rao", "Manager", "o1")
        var att: AttendanceTodayDto? =
            AttendanceTodayDto("2026-07-27", AttendanceRecordDto("Present", "09:00", null, 120), false)
        var bal: List<BalanceRowDto>? = listOf(BalanceRowDto("Casual", 12.0, 3.0, 0.0, 9.0))
        var exp: List<ExpenseDto>? = listOf(ExpenseDto("e1", "Travel", 500.0, "Cab", "Uber", "2026-07-20"))
        var failMe = false; var failAtt = false; var failBal = false; var failExp = false
        var clockedIn = false; var clockedOut = false

        override suspend fun me() = if (failMe) throw IOException("x") else me!!
        override suspend fun attendanceToday() = if (failAtt) throw IOException("x") else att!!
        override suspend fun clockIn(body: ClockBody): AttendanceRecordDto { clockedIn = true; return att!!.record!! }
        override suspend fun clockOut(body: ClockBody): AttendanceRecordDto { clockedOut = true; return att!!.record!! }
        override suspend fun leaveBalances() = if (failBal) throw IOException("x") else bal!!
        override suspend fun expenses() = if (failExp) throw IOException("x") else exp!!
    }

    private fun moshi() = Moshi.Builder().add(KotlinJsonAdapterFactory()).build()

    @Test
    fun manager_refresh_caches_all_sections() = runTest {
        val repo = ProfileRepository(FakeApi(), FakeDao(), moshi())
        assertTrue(repo.refresh(includeExpenses = true))
        val b = repo.profile.first()!!
        assertEquals("a@b.com", b.me?.email)
        assertEquals(1, b.balances.size)
        assertEquals(1, b.expenses.size)
        assertTrue(b.isClockedIn)                    // clock_in set, clock_out null
    }

    @Test
    fun non_manager_refresh_skips_expenses_but_succeeds() = runTest {
        val api = FakeApi()
        val repo = ProfileRepository(api, FakeDao(), moshi())
        assertTrue(repo.refresh(includeExpenses = false))
        val b = repo.profile.first()!!
        assertEquals(1, b.balances.size)
        assertTrue(b.expenses.isEmpty())             // never fetched
        assertFalse(api.failExp)                     // and the endpoint wasn't hit
    }

    @Test
    fun partial_failure_keeps_previous_copy() = runTest {
        val dao = FakeDao()
        val api = FakeApi()
        val repo = ProfileRepository(api, dao, moshi())
        assertTrue(repo.refresh(includeExpenses = true))

        api.failBal = true
        api.me = ProfileMeDto("u1", "new@b.com", "A", "R", "Manager", "o1")
        assertTrue(repo.refresh(includeExpenses = true))

        val b = repo.profile.first()!!
        assertEquals("new@b.com", b.me?.email)       // updated
        assertEquals(1, b.balances.size)             // previous balances retained
    }

    @Test
    fun total_failure_returns_false_and_keeps_cache() = runTest {
        val dao = FakeDao()
        val api = FakeApi()
        val repo = ProfileRepository(api, dao, moshi())
        assertTrue(repo.refresh(includeExpenses = true))

        api.failMe = true; api.failAtt = true; api.failBal = true; api.failExp = true
        assertFalse(repo.refresh(includeExpenses = true))
        assertEquals("a@b.com", repo.profile.first()?.me?.email)
    }

    @Test
    fun clock_in_posts_and_resyncs() = runTest {
        val api = FakeApi()
        val repo = ProfileRepository(api, FakeDao(), moshi())
        assertTrue(repo.clockIn(includeExpenses = false))
        assertTrue(api.clockedIn)
        assertNotNull(repo.profile.first()?.attendance)
    }

    @Test
    fun clocked_out_record_is_not_clocked_in() = runTest {
        val api = FakeApi().apply {
            att = AttendanceTodayDto("2026-07-27",
                AttendanceRecordDto("Present", "09:00", "17:00", 480), false)
        }
        val repo = ProfileRepository(api, FakeDao(), moshi())
        assertTrue(repo.refresh(includeExpenses = false))
        assertFalse(repo.profile.first()!!.isClockedIn)
    }
}
