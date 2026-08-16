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
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.PATCH
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query as HttpQuery
import javax.inject.Inject
import javax.inject.Singleton

// ---- Wire DTO (subset of the backend Lead response the mobile list needs) ----

@JsonClass(generateAdapter = true)
data class LeadStageDto(
    val id: String? = null,
    val name: String? = null,
)

@JsonClass(generateAdapter = true)
data class LeadDto(
    val id: String = "",
    val title: String = "",
    val first_name: String? = null,
    val last_name: String? = null,
    val phone: String? = null,          // already masked server-side for telecallers
    val status: String? = "New",
    val value: Double? = null,
    val priority: String? = "Medium",
    val assigned_user_id: String? = null,
    val updated_at: String? = null,
    val stage: LeadStageDto? = null,
)

@JsonClass(generateAdapter = true)
data class LeadCreateReq(
    val title: String,
    val first_name: String? = null,
    val phone: String? = null,
    val status: String = "New",
    val priority: String = "Medium",
    val value: Double = 0.0,
)

@JsonClass(generateAdapter = true)
data class LeadUpdateReq(
    val status: String? = null,
    val priority: String? = null,
)

interface LeadApi {
    @GET("leads/")
    suspend fun list(
        @HttpQuery("updated_after") updatedAfter: String? = null,
        @HttpQuery("limit") limit: Int = 100,
    ): List<LeadDto>

    @POST("leads/")
    suspend fun create(@Body body: LeadCreateReq): LeadDto

    @PATCH("leads/{id}")
    suspend fun update(@Path("id") id: String, @Body body: LeadUpdateReq): LeadDto
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
    @Query("SELECT * FROM leads ORDER BY updatedAt DESC, title ASC")
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
    title = title.ifBlank { "Untitled Lead" },
    name = listOfNotNull(first_name, last_name).filter { it.isNotBlank() }.joinToString(" ").ifBlank { title.ifBlank { "Lead" } },
    phone = phone,
    status = stage?.name?.takeIf { it.isNotBlank() } ?: status ?: "New",
    value = value ?: 0.0,
    priority = priority ?: "Medium",
    updatedAt = updated_at,
)

private fun LeadEntity.toDomain() = Lead(id, title, name, phone, status, value, priority)

/**
 * Offline-first: the UI observes the Room cache (single source of truth); a
 * refresh performs a pull and upserts. A network failure leaves the
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

    suspend fun updateStatus(id: String, newStatus: String): Boolean = runCatching {
        val updated = api.update(id, LeadUpdateReq(status = newStatus))
        dao.upsertAll(listOf(updated.toEntity()))
        true
    }.getOrDefault(false)

    suspend fun createLead(
        name: String,
        title: String,
        phone: String?,
        priority: String = "Medium",
        value: Double = 0.0
    ): Boolean = runCatching {
        val created = api.create(LeadCreateReq(
            title = title.ifBlank { name },
            first_name = name,
            phone = phone,
            status = "New",
            priority = priority,
            value = value
        ))
        dao.upsertAll(listOf(created.toEntity()))
        true
    }.getOrDefault(false)
}
