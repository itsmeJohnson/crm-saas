package com.crm.mobile.feature.reminders

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
import java.time.Instant
import java.time.ZoneId

class ReminderRepositoryTest {

    private class FakeDao(private val stored: MutableList<ReminderEntity> = mutableListOf()) : ReminderDao {
        override fun observeAll(): Flow<List<ReminderEntity>> = flow { emit(stored.toList()) }
        override suspend fun upsertAll(rows: List<ReminderEntity>) { stored.addAll(rows) }
        override suspend fun clear() { stored.clear() }
    }

    private class FakeApi(
        var rows: List<ReminderDto> = emptyList(),
        val failList: Boolean = false,
    ) : ReminderApi {
        var lastPatchId: String? = null
        var lastPatch: ReminderPatch? = null
        var completedId: String? = null

        override suspend fun list(limit: Int): List<ReminderDto> {
            if (failList) throw IOException("offline"); return rows
        }
        override suspend fun patch(id: String, body: ReminderPatch): ReminderDto {
            lastPatchId = id; lastPatch = body
            return rows.first { it.id == id }.copy(remind_at = body.remind_at)
        }
        override suspend fun complete(id: String): ReminderDto {
            completedId = id
            return rows.first { it.id == id }.copy(status = "Done", completed_at = "2026-07-26T12:00:00Z")
        }
    }

    private fun dto(id: String, remindAt: String?, status: String = "Pending", leadId: String? = null) =
        ReminderDto(id, "Call $id", null, "High", status, null, remindAt, null, leadId, "2026-07-26T09:00:00Z")

    @Test
    fun refresh_caches_only_tasks_that_carry_a_remind_at() = runTest {
        val api = FakeApi(listOf(
            dto("r1", "2026-07-26T09:00:00Z"),
            dto("noremind", null),          // a plain task — not a reminder
            dto("r2", "2026-07-27T09:00:00Z"),
        ))
        val repo = ReminderRepository(api, FakeDao())
        assertTrue(repo.refresh())
        assertEquals(listOf("r1", "r2"), repo.reminders.first().map { it.id }.sorted())
    }

    @Test
    fun refresh_offline_keeps_cache() = runTest {
        val cached = mutableListOf(
            ReminderEntity("c1", "Cached", null, "Low", "Pending", null, "2026-07-20T09:00:00Z", null, null),
        )
        val repo = ReminderRepository(FakeApi(failList = true), FakeDao(cached))
        assertFalse(repo.refresh())
        assertEquals("Cached", repo.reminders.first().single().title)
    }

    @Test
    fun snooze_patches_remind_at_with_iso_and_resyncs() = runTest {
        val api = FakeApi(listOf(dto("r1", "2026-07-26T09:00:00Z")))
        val repo = ReminderRepository(api, FakeDao())
        val newMs = 1_800_000_000_000L
        assertTrue(repo.snooze("r1", newMs))
        assertEquals("r1", api.lastPatchId)
        assertEquals(Instant.ofEpochMilli(newMs).toString(), api.lastPatch?.remind_at)
    }

    @Test
    fun complete_calls_endpoint() = runTest {
        val api = FakeApi(listOf(dto("r1", "2026-07-26T09:00:00Z")))
        val repo = ReminderRepository(api, FakeDao())
        assertTrue(repo.complete("r1"))
        assertEquals("r1", api.completedId)
    }

    @Test
    fun bucket_partitions_by_remind_at_and_status() {
        val start = 1_000L; val end = 2_000L
        fun r(ms: Long, done: Boolean = false) =
            Reminder("x", "t", null, "High", if (done) "Done" else "Pending", ms, null, null)
        assertEquals(ReminderBucket.OVERDUE, r(500).bucket(start, end))
        assertEquals(ReminderBucket.TODAY, r(1_500).bucket(start, end))
        assertEquals(ReminderBucket.UPCOMING, r(2_500).bucket(start, end))
        assertEquals(ReminderBucket.COMPLETED, r(500, done = true).bucket(start, end))
    }

    @Test
    fun snooze_option_one_hour_is_exact() {
        val now = 1_800_000_000_000L
        assertEquals(now + 3_600_000L, SnoozeOption.ONE_HOUR.nextMillis(now, ZoneId.of("UTC")))
    }

    @Test
    fun snooze_option_tomorrow_is_next_day_at_9am_local() {
        val zone = ZoneId.of("UTC")
        // 2026-07-26T15:00:00Z
        val now = Instant.parse("2026-07-26T15:00:00Z").toEpochMilli()
        val next = SnoozeOption.TOMORROW.nextMillis(now, zone)
        assertEquals(Instant.parse("2026-07-27T09:00:00Z"), Instant.ofEpochMilli(next))
    }

    @Test
    fun moshi_parses_task_shaped_json_ignoring_extra_fields() {
        val moshi = Moshi.Builder().add(KotlinJsonAdapterFactory()).build()
        val json = """
            {"id":"r1","organization_id":"o1","title":"Follow up Amit","description":null,
             "priority":"High","status":"Pending","due_date":null,
             "remind_at":"2026-07-27T09:00:00Z","completed_at":null,
             "assigned_user_id":null,"created_by":"u1","lead_id":"l9","recurrence":"none",
             "checklist":null,"created_at":"2026-07-26T09:00:00Z","updated_at":"2026-07-26T09:00:00Z"}
        """.trimIndent()
        val dto = moshi.adapter(ReminderDto::class.java).fromJson(json)!!
        assertEquals("r1", dto.id)
        assertEquals("2026-07-27T09:00:00Z", dto.remind_at)
        assertEquals("l9", dto.lead_id)
    }

    @Test
    fun moshi_serializes_patch_with_only_remind_at() {
        val moshi = Moshi.Builder().add(KotlinJsonAdapterFactory()).build()
        val out = moshi.adapter(ReminderPatch::class.java).toJson(ReminderPatch("2026-07-27T09:00:00Z"))
        assertEquals("""{"remind_at":"2026-07-27T09:00:00Z"}""", out)
        assertNull(Regex("due_date").find(out))
    }
}
