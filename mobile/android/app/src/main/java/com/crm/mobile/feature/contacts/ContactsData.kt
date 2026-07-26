package com.crm.mobile.feature.contacts

import androidx.room.Dao
import androidx.room.Delete
import androidx.room.Entity
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.PrimaryKey
import androidx.room.Query
import com.crm.mobile.feature.tasks.parseIsoMillis
import com.squareup.moshi.JsonAdapter
import com.squareup.moshi.JsonClass
import com.squareup.moshi.Moshi
import com.squareup.moshi.Types
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.combine
import retrofit2.http.GET
import retrofit2.http.Path
import retrofit2.http.Query as HttpQuery
import javax.inject.Inject
import javax.inject.Singleton

// ---- Wire DTOs ----

@JsonClass(generateAdapter = true)
data class ContactDto(
    val id: String,
    val first_name: String,
    val last_name: String,
    val email: String?,
    val phone: String?,
    val job_title: String?,
    val tags: List<String>?,
)

@JsonClass(generateAdapter = true)
data class ContactTimelineDto(
    val id: String,
    val type: String,
    val title: String,
    val description: String?,
    val timestamp: String,
)

interface ContactApi {
    @GET("contacts/")
    suspend fun list(@HttpQuery("limit") limit: Int = 100): List<ContactDto>

    @GET("contacts/{id}/timeline")
    suspend fun timeline(@Path("id") id: String): List<ContactTimelineDto>
}

// ---- Local cache + local-only favorites ----

@Entity(tableName = "contacts")
data class ContactEntity(
    @PrimaryKey val id: String,
    val name: String,
    val email: String?,
    val phone: String?,
    val jobTitle: String?,
    val tagsJson: String?,
)

@Entity(tableName = "contact_favorites")
data class ContactFavoriteEntity(@PrimaryKey val contactId: String)

@Dao
interface ContactDao {
    @Query("SELECT * FROM contacts ORDER BY name")
    fun observeAll(): Flow<List<ContactEntity>>

    @Query("SELECT * FROM contacts WHERE id = :id LIMIT 1")
    suspend fun byId(id: String): ContactEntity?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertAll(rows: List<ContactEntity>)

    @Query("DELETE FROM contacts")
    suspend fun clear()

    @Query("SELECT contactId FROM contact_favorites")
    fun observeFavoriteIds(): Flow<List<String>>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun addFavorite(fav: ContactFavoriteEntity)

    @Delete
    suspend fun removeFavorite(fav: ContactFavoriteEntity)

    @Query("SELECT EXISTS(SELECT 1 FROM contact_favorites WHERE contactId = :id)")
    suspend fun isFavorite(id: String): Boolean
}

// ---- Domain ----

data class Contact(
    val id: String,
    val name: String,
    val email: String?,
    val phone: String?,
    val jobTitle: String?,
    val tags: List<String>,
    val isFavorite: Boolean,
)

data class ContactTimelineItem(
    val id: String,
    val type: String,
    val title: String,
    val description: String?,
    val timestampMillis: Long?,
)

@Singleton
class ContactRepository @Inject constructor(
    private val api: ContactApi,
    private val dao: ContactDao,
    moshi: Moshi,
) {
    private val tagsAdapter: JsonAdapter<List<String>> =
        moshi.adapter(Types.newParameterizedType(List::class.java, String::class.java))

    val contacts: Flow<List<Contact>> =
        combine(dao.observeAll(), dao.observeFavoriteIds()) { list, favIds ->
            val favs = favIds.toSet()
            list.map { it.toDomain(tagsAdapter, it.id in favs) }
        }

    suspend fun refresh(): Boolean = runCatching {
        val fresh = api.list().map { it.toEntity(tagsAdapter) }
        dao.clear()
        dao.upsertAll(fresh)
        true
    }.getOrDefault(false)

    suspend fun contact(id: String): Contact? =
        dao.byId(id)?.toDomain(tagsAdapter, dao.isFavorite(id))

    suspend fun toggleFavorite(id: String) {
        if (dao.isFavorite(id)) dao.removeFavorite(ContactFavoriteEntity(id))
        else dao.addFavorite(ContactFavoriteEntity(id))
    }

    suspend fun timeline(id: String): Result<List<ContactTimelineItem>> =
        runCatching {
            api.timeline(id).map { ContactTimelineItem(it.id, it.type, it.title, it.description, parseIsoMillis(it.timestamp)) }
        }
}

private fun ContactDto.toEntity(adapter: JsonAdapter<List<String>>) = ContactEntity(
    id = id,
    name = listOf(first_name, last_name).joinToString(" ").trim(),
    email = email, phone = phone, jobTitle = job_title,
    tagsJson = tags?.let { adapter.toJson(it) },
)

private fun ContactEntity.toDomain(adapter: JsonAdapter<List<String>>, favorite: Boolean) = Contact(
    id = id, name = name, email = email, phone = phone, jobTitle = jobTitle,
    tags = tagsJson?.let { runCatching { adapter.fromJson(it) }.getOrNull() }.orEmpty(),
    isFavorite = favorite,
)
