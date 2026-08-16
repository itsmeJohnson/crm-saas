package com.crm.mobile.feature.tasks

import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.IOException

class TaskRepositoryTest {

    private val START = 1_000_000L   // "today" window
    private val END = 2_000_000L

    private fun task(status: String = "Todo", due: Long? = null) =
        Task("t", "Call back", null, "Medium", status, due)

    @Test
    fun bucket_classifies_every_case() {
        assertEquals(TaskBucket.COMPLETED, task(status = "Done", due = START + 10).bucket(START, END))
        assertEquals(TaskBucket.OVERDUE, task(due = START - 10).bucket(START, END))
        assertEquals(TaskBucket.TODAY, task(due = START + 10).bucket(START, END))
        assertEquals(TaskBucket.UPCOMING, task(due = END + 10).bucket(START, END))
        assertEquals(TaskBucket.UPCOMING, task(due = null).bucket(START, END))
        // a due-but-Done task is Completed, never Overdue
        assertEquals(TaskBucket.COMPLETED, task(status = "Done", due = START - 999).bucket(START, END))
    }

    @Test
    fun parseIsoMillis_handles_z_and_offset_and_garbage() {
        assertEquals(0L, parseIsoMillis("1970-01-01T00:00:00Z"))
        assertTrue((parseIsoMillis("2026-07-26T10:00:00+05:30") ?: -1) > 0)
        assertEquals(null, parseIsoMillis("not-a-date"))
        assertEquals(null, parseIsoMillis(null))
    }

    // ---- offline-first repository ----

    private class FakeDao(private val stored: MutableList<TaskEntity> = mutableListOf()) : TaskDao {
        var upserted: List<TaskEntity>? = null
        override fun observeAll(): Flow<List<TaskEntity>> = flow { emit(stored.toList()) }
        override suspend fun upsertAll(tasks: List<TaskEntity>) { upserted = tasks; stored.addAll(tasks) }
        override suspend fun clear() { stored.clear() }
    }

    private class FakeApi(val result: List<TaskDto> = emptyList(), val fail: Boolean = false) : TaskApi {
        override suspend fun list(): List<TaskDto> { if (fail) throw IOException("offline"); return result }
        override suspend fun complete(id: String) = result.first()
    }

    @Test
    fun refresh_success_caches() = runTest {
        val api = FakeApi(listOf(TaskDto("1", "A", null, "High", "Todo", null, null, null, "2026-07-26T00:00:00Z")))
        val repo = TaskRepository(api, FakeDao())
        assertTrue(repo.refresh())
        assertEquals("A", repo.tasks.first().single().title)
    }

    @Test
    fun refresh_offline_keeps_cache() = runTest {
        val cached = mutableListOf(TaskEntity("1", "Cached", null, "Low", "Todo", null, null, null))
        val repo = TaskRepository(FakeApi(fail = true), FakeDao(cached))
        assertFalse(repo.refresh())
        assertEquals("Cached", repo.tasks.first().single().title)
    }
}
