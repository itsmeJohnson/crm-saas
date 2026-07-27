package com.crm.mobile.feature.reports

import androidx.room.Dao
import androidx.room.Entity
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.PrimaryKey
import androidx.room.Query
import com.squareup.moshi.JsonClass
import com.squareup.moshi.Moshi
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import retrofit2.http.GET
import javax.inject.Inject
import javax.inject.Singleton

// ---- Wire DTOs (subsets; Moshi ignores extra fields) ----

/** A labelled count — the common shape of task by_priority/by_status and
 *  communication by_channel buckets, reused for every bar chart. */
@JsonClass(generateAdapter = true)
data class LabelCount(val label: String, val count: Int)

@JsonClass(generateAdapter = true)
data class DashSummaryDto(
    val total_leads: Int = 0,
    val contacts_count: Int = 0,
    val companies_count: Int = 0,
    val activities_count: Int = 0,
    val conversion_rate: Double? = null,
    val leads_by_status: Map<String, Int> = emptyMap(),
)

@JsonClass(generateAdapter = true)
data class TaskReportDto(
    val total: Int = 0,
    val open: Int = 0,
    val completed: Int = 0,
    val overdue: Int = 0,
    val due_today: Int = 0,
    val completion_rate: Double = 0.0,
    val by_priority: List<LabelCount> = emptyList(),
    val by_status: List<LabelCount> = emptyList(),
)

@JsonClass(generateAdapter = true)
data class CommOverviewDto(
    val total: Int = 0,
    val outbound: Int = 0,
    val inbound: Int = 0,
    val delivered: Int = 0,
    val failed: Int = 0,
    val delivery_rate: Double = 0.0,
    val by_channel: List<LabelCount> = emptyList(),
)

interface ReportsApi {
    @GET("dashboard/summary")
    suspend fun dashboardSummary(): DashSummaryDto

    @GET("tasks/reports")
    suspend fun taskReport(): TaskReportDto

    @GET("communication-analytics/overview")
    suspend fun commOverview(): CommOverviewDto
}

// ---- Local cache: a single snapshot row holding the three report JSON blobs ----

@Entity(tableName = "reports_snapshot")
data class ReportsSnapshotEntity(
    @PrimaryKey val id: String = "me",
    val dashboardJson: String?,
    val taskJson: String?,
    val commJson: String?,
    val cachedAt: Long,
)

@Dao
interface ReportsDao {
    @Query("SELECT * FROM reports_snapshot WHERE id = 'me'")
    fun observe(): Flow<ReportsSnapshotEntity?>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(row: ReportsSnapshotEntity)
}

// ---- Domain ----

data class ReportsBundle(
    val dashboard: DashSummaryDto?,
    val tasks: TaskReportDto?,
    val comm: CommOverviewDto?,
    val cachedAt: Long,
)

/**
 * Offline-first: the UI observes the cached snapshot (renders instantly, works
 * offline). A refresh fetches the three reports independently — a partial
 * failure keeps the previous copy of whatever didn't load, so one manager-gated
 * or flaky endpoint never blanks the whole screen. Returns false only when ALL
 * three fail (treated as "offline").
 */
@Singleton
class ReportsRepository @Inject constructor(
    private val api: ReportsApi,
    private val dao: ReportsDao,
    moshi: Moshi,
) {
    private val dashAdapter = moshi.adapter(DashSummaryDto::class.java)
    private val taskAdapter = moshi.adapter(TaskReportDto::class.java)
    private val commAdapter = moshi.adapter(CommOverviewDto::class.java)

    val reports: Flow<ReportsBundle?> = dao.observe().map { row -> row?.let { toDomain(it) } }

    suspend fun refresh(): Boolean {
        val prev = dao.observe().first()
        val dash = runCatching { api.dashboardSummary() }.getOrNull()
        val task = runCatching { api.taskReport() }.getOrNull()
        val comm = runCatching { api.commOverview() }.getOrNull()
        if (dash == null && task == null && comm == null) return false
        dao.upsert(
            ReportsSnapshotEntity(
                dashboardJson = dash?.let { dashAdapter.toJson(it) } ?: prev?.dashboardJson,
                taskJson = task?.let { taskAdapter.toJson(it) } ?: prev?.taskJson,
                commJson = comm?.let { commAdapter.toJson(it) } ?: prev?.commJson,
                cachedAt = System.currentTimeMillis(),
            ),
        )
        return true
    }

    private fun toDomain(row: ReportsSnapshotEntity) = ReportsBundle(
        dashboard = row.dashboardJson?.let { runCatching { dashAdapter.fromJson(it) }.getOrNull() },
        tasks = row.taskJson?.let { runCatching { taskAdapter.fromJson(it) }.getOrNull() },
        comm = row.commJson?.let { runCatching { commAdapter.fromJson(it) }.getOrNull() },
        cachedAt = row.cachedAt,
    )
}
