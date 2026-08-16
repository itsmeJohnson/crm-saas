package com.crm.mobile.feature.leads

import androidx.room.Dao
import androidx.room.Entity
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.PrimaryKey
import androidx.room.Query
import com.squareup.moshi.JsonClass
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import retrofit2.http.GET
import retrofit2.http.Query as HttpQuery
import javax.inject.Inject
import javax.inject.Singleton

// ---- Wire DTO (subset of the backend Lead response the mobile list needs) ----

@JsonClass(generateAdapter = true)
data class LeadDto(
    val id: String,
    val title: String,
    val first_name: String?,
    val last_name: String?,
    val phone: String?,          // already masked server-side for telecallers
    val status: String,
    val value: Double?,
    val priority: String,
    val assigned_user_id: String?,
    val updated_at: String?,
)

interface LeadApi {
    // Offline-first delta pull: `updated_after` is Gap B (backend work). Until it
    // lands the app falls back to a full page; the param is simply ignored.
    @GET("leads")
    suspend fun list(
        @HttpQuery("updated_after") updatedAfter: String? = null,
        @HttpQuery("limit") limit: Int = 100,
    ): List<LeadDto>
}

// ---- Local cache ----

@Entity(tableName = "leads")
data class LeadEntity(
    @PrimaryKey val id: String,
    val title: String,
    val name: String,
    val phone: String?,
    val status: String,
    val value: Double?,
    val priority: String,
    val updatedAt: String?,
)

@Dao
interface LeadDao {
    @Query("SELECT * FROM leads ORDER BY title")
    fun observeAll(): Flow<List<LeadEntity>>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertAll(leads: List<LeadEntity>)

    @Query("SELECT MAX(updatedAt) FROM leads")
    suspend fun latestUpdatedAt(): String?

    @Query("DELETE FROM leads")
    suspend fun clear()
}

// ---- Domain ----

data class Lead(
    val id: String,
    val title: String,
    val name: String,
    val phone: String?,
    val status: String,
    val value: Double?,
    val priority: String,
)

private fun LeadDto.toEntity() = LeadEntity(
    id = id,
    title = title,
    name = listOfNotNull(first_name, last_name).joinToString(" ").ifBlank { "—" },
    phone = phone,
    status = status,
    value = value,
    priority = priority,
    updatedAt = updated_at,
)

private fun LeadEntity.toDomain() = Lead(id, title, name, phone, status, value, priority)

/**
 * Offline-first: the UI observes the Room cache (single source of truth); a
 * refresh performs an incremental pull and upserts. A network failure leaves the
 * cached list intact — the screen keeps working offline.
 */
@Singleton
class LeadRepository @Inject constructor(
    private val api: LeadApi,
    private val dao: LeadDao,
) {
    val leads: Flow<List<Lead>> = dao.observeAll().map { list -> list.map { it.toDomain() } }

    /** Returns true on a successful network refresh, false if offline (cache kept). */
    suspend fun refresh(): Boolean = runCatching {
        val since = dao.latestUpdatedAt()
        val fresh = api.list(updatedAfter = since)
        dao.upsertAll(fresh.map { it.toEntity() })
        true
    }.getOrDefault(false)
}
