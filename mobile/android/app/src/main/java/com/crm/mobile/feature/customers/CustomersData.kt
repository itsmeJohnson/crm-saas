package com.crm.mobile.feature.customers

import androidx.room.Dao
import androidx.room.Entity
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.PrimaryKey
import androidx.room.Query
import com.crm.mobile.feature.tasks.parseIsoMillis
import com.squareup.moshi.JsonClass
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import retrofit2.http.GET
import retrofit2.http.Path
import javax.inject.Inject
import javax.inject.Singleton

// ---- Wire DTOs ----

@JsonClass(generateAdapter = true)
data class CustomerListItemDto(
    val company_id: String,
    val name: String,
    val industry: String?,
    val order_count: Int = 0,
    val total_invoiced: Double = 0.0,
    val outstanding_balance: Double = 0.0,
)

@JsonClass(generateAdapter = true)
data class TimelineEventDto(
    val id: String,
    val type: String,
    val group: String,
    val title: String,
    val description: String?,
    val actor_name: String?,
    val source: String,
    val timestamp: String,
)

interface CustomerApi {
    @GET("customers/")
    suspend fun list(): List<CustomerListItemDto>

    @GET("customers/{id}/timeline")
    suspend fun timeline(@Path("id") companyId: String): List<TimelineEventDto>
}

// ---- Local cache (list) ----

@Entity(tableName = "customers")
data class CustomerEntity(
    @PrimaryKey val companyId: String,
    val name: String,
    val industry: String?,
    val orderCount: Int,
    val totalInvoiced: Double,
    val outstandingBalance: Double,
)

@Dao
interface CustomerDao {
    @Query("SELECT * FROM customers ORDER BY name")
    fun observeAll(): Flow<List<CustomerEntity>>

    @Query("SELECT * FROM customers WHERE companyId = :id LIMIT 1")
    suspend fun byId(id: String): CustomerEntity?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertAll(rows: List<CustomerEntity>)

    @Query("DELETE FROM customers")
    suspend fun clear()
}

// ---- Domain ----

data class Customer(
    val companyId: String,
    val name: String,
    val industry: String?,
    val orderCount: Int,
    val totalInvoiced: Double,
    val outstandingBalance: Double,
)

data class TimelineEvent(
    val id: String,
    val type: String,
    val group: String,
    val title: String,
    val description: String?,
    val actorName: String?,
    val timestampMillis: Long?,
)

private fun CustomerListItemDto.toEntity() =
    CustomerEntity(company_id, name, industry, order_count, total_invoiced, outstanding_balance)

private fun CustomerEntity.toDomain() =
    Customer(companyId, name, industry, orderCount, totalInvoiced, outstandingBalance)

private fun TimelineEventDto.toDomain() =
    TimelineEvent(id, type, group, title, description, actor_name, parseIsoMillis(timestamp))

/** Offline-first list cache + client-side search; the unified timeline is fetched
 *  live (online) per customer. */
@Singleton
class CustomerRepository @Inject constructor(
    private val api: CustomerApi,
    private val dao: CustomerDao,
) {
    val customers: Flow<List<Customer>> = dao.observeAll().map { list -> list.map { it.toDomain() } }

    suspend fun refresh(): Boolean = runCatching {
        val fresh = api.list().map { it.toEntity() }
        dao.clear()
        dao.upsertAll(fresh)
        true
    }.getOrDefault(false)

    suspend fun customer(companyId: String): Customer? = dao.byId(companyId)?.toDomain()

    /** Result so the detail screen can show an offline message rather than crash. */
    suspend fun timeline(companyId: String): Result<List<TimelineEvent>> =
        runCatching { api.timeline(companyId).map { it.toDomain() } }
}
