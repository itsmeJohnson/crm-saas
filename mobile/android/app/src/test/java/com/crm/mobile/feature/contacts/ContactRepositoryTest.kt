package com.crm.mobile.feature.contacts

import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.IOException

class ContactRepositoryTest {

    private val moshi = Moshi.Builder().add(KotlinJsonAdapterFactory()).build()

    private class FakeDao(private val stored: MutableList<ContactEntity> = mutableListOf()) : ContactDao {
        private val favs = MutableStateFlow<List<String>>(emptyList())
        override fun observeAll(): Flow<List<ContactEntity>> = flow { emit(stored.toList()) }
        override suspend fun byId(id: String) = stored.find { it.id == id }
        override suspend fun upsertAll(rows: List<ContactEntity>) { stored.addAll(rows) }
        override suspend fun clear() { stored.clear() }
        override fun observeFavoriteIds(): Flow<List<String>> = favs
        override suspend fun addFavorite(fav: ContactFavoriteEntity) { favs.value = favs.value + fav.contactId }
        override suspend fun removeFavorite(fav: ContactFavoriteEntity) { favs.value = favs.value - fav.contactId }
        override suspend fun isFavorite(id: String) = id in favs.value
    }

    private class FakeApi(
        val listResult: List<ContactDto> = emptyList(),
        val fail: Boolean = false,
    ) : ContactApi {
        override suspend fun list(limit: Int): List<ContactDto> { if (fail) throw IOException("offline"); return listResult }
        override suspend fun timeline(id: String): List<ContactTimelineDto> { if (fail) throw IOException("offline"); return emptyList() }
    }

    private fun repo(api: FakeApi, dao: FakeDao = FakeDao()) = ContactRepository(api, dao, moshi)

    @Test
    fun refresh_caches_and_parses_tags() = runTest {
        val api = FakeApi(listOf(ContactDto("c1", "Amit", "Kumar", "a@x.com", "123", "Manager", listOf("VIP", "Hot"))))
        val r = repo(api)
        assertTrue(r.refresh())
        val c = r.contacts.first().single()
        assertEquals("Amit Kumar", c.name)
        assertEquals(listOf("VIP", "Hot"), c.tags)
        assertFalse(c.isFavorite)
    }

    @Test
    fun refresh_offline_keeps_cache() = runTest {
        val dao = FakeDao(mutableListOf(ContactEntity("c1", "Cached", null, null, null, null)))
        val r = repo(FakeApi(fail = true), dao)
        assertFalse(r.refresh())
        assertEquals("Cached", r.contacts.first().single().name)
    }

    @Test
    fun toggle_favorite_is_local_and_reversible() = runTest {
        val dao = FakeDao(mutableListOf(ContactEntity("c1", "Amit", null, null, null, null)))
        val r = repo(FakeApi(), dao)
        assertFalse(r.contact("c1")!!.isFavorite)
        r.toggleFavorite("c1")
        assertTrue(r.contact("c1")!!.isFavorite)
        r.toggleFavorite("c1")
        assertFalse(r.contact("c1")!!.isFavorite)
    }
}
