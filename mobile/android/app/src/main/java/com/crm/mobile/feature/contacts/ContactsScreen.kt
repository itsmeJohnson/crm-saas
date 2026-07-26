package com.crm.mobile.feature.contacts

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import java.util.Date
import javax.inject.Inject

// ---------- List ----------

@HiltViewModel
class ContactsViewModel @Inject constructor(private val repo: ContactRepository) : ViewModel() {
    private val _query = MutableStateFlow("")
    val query: StateFlow<String> = _query.asStateFlow()
    private val _tag = MutableStateFlow<String?>(null)
    val tag: StateFlow<String?> = _tag.asStateFlow()
    private val _favOnly = MutableStateFlow(false)
    val favOnly: StateFlow<Boolean> = _favOnly.asStateFlow()
    private val _loading = MutableStateFlow(true)
    val loading: StateFlow<Boolean> = _loading.asStateFlow()
    private val _offline = MutableStateFlow(false)
    val offline: StateFlow<Boolean> = _offline.asStateFlow()

    val tags: StateFlow<List<String>> = repo.contacts
        .map { cs -> cs.flatMap { it.tags }.distinct().sorted() }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())

    val visible: StateFlow<List<Contact>> =
        combine(repo.contacts, _query, _tag, _favOnly) { list, q, tag, favOnly ->
            list.filter { q.isBlank() || it.name.contains(q, true) || it.email?.contains(q, true) == true }
                .filter { tag == null || tag in it.tags }
                .filter { !favOnly || it.isFavorite }
        }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())

    init { refresh() }
    fun refresh() { _loading.value = true; viewModelScope.launch { _offline.value = !repo.refresh(); _loading.value = false } }
    fun setQuery(q: String) { _query.value = q }
    fun selectTag(t: String?) { _tag.value = if (_tag.value == t) null else t }
    fun toggleFavOnly() { _favOnly.value = !_favOnly.value }
    fun toggleFavorite(id: String) { viewModelScope.launch { repo.toggleFavorite(id) } }
}

@Composable
fun ContactsListScreen(onOpen: (String) -> Unit, vm: ContactsViewModel = hiltViewModel()) {
    val query by vm.query.collectAsStateWithLifecycle()
    val tag by vm.tag.collectAsStateWithLifecycle()
    val favOnly by vm.favOnly.collectAsStateWithLifecycle()
    val tags by vm.tags.collectAsStateWithLifecycle()
    val loading by vm.loading.collectAsStateWithLifecycle()
    val offline by vm.offline.collectAsStateWithLifecycle()
    val contacts by vm.visible.collectAsStateWithLifecycle()

    Column(Modifier.fillMaxSize().padding(horizontal = 12.dp)) {
        if (offline) Text("Offline — showing cached contacts", color = MaterialTheme.colorScheme.error,
            style = MaterialTheme.typography.labelMedium, modifier = Modifier.padding(vertical = 8.dp))
        OutlinedTextField(query, vm::setQuery, label = { Text("Search contacts") }, singleLine = true,
            modifier = Modifier.fillMaxWidth().padding(top = 8.dp))
        Row(Modifier.fillMaxWidth().padding(vertical = 8.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            FilterChip(selected = favOnly, onClick = vm::toggleFavOnly, label = { Text("★ Favorites") })
            tags.take(4).forEach { t ->
                FilterChip(selected = tag == t, onClick = { vm.selectTag(t) }, label = { Text(t) })
            }
        }
        when {
            loading && contacts.isEmpty() ->
                Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
            contacts.isEmpty() -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { Text("No contacts") }
            else -> LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                items(contacts, key = { it.id }) { c ->
                    Card(Modifier.fillMaxWidth().clickable { onOpen(c.id) }) {
                        Row(Modifier.padding(14.dp).fillMaxWidth(), verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.SpaceBetween) {
                            Column(Modifier.padding(end = 8.dp)) {
                                Text(c.name, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Medium)
                                val sub = listOfNotNull(c.jobTitle, c.phone ?: c.email).joinToString(" · ")
                                if (sub.isNotBlank()) Text(sub, style = MaterialTheme.typography.bodySmall)
                            }
                            Text(if (c.isFavorite) "★" else "☆",
                                modifier = Modifier.clickable { vm.toggleFavorite(c.id) })
                        }
                    }
                }
            }
        }
    }
}

// ---------- Detail ----------

data class ContactDetailState(
    val loading: Boolean = true,
    val offline: Boolean = false,
    val contact: Contact? = null,
    val timeline: List<ContactTimelineItem> = emptyList(),
)

@HiltViewModel
class ContactDetailViewModel @Inject constructor(
    savedStateHandle: SavedStateHandle,
    private val repo: ContactRepository,
) : ViewModel() {
    private val id: String = savedStateHandle["contactId"] ?: ""
    private val _state = MutableStateFlow(ContactDetailState())
    val state: StateFlow<ContactDetailState> = _state.asStateFlow()

    init { load() }

    private fun load() {
        viewModelScope.launch {
            val header = repo.contact(id)
            repo.timeline(id)
                .onSuccess { _state.value = ContactDetailState(false, false, header, it) }
                .onFailure { _state.value = ContactDetailState(false, true, header, emptyList()) }
        }
    }

    fun toggleFavorite() {
        viewModelScope.launch {
            repo.toggleFavorite(id)
            _state.value = _state.value.copy(contact = repo.contact(id))
        }
    }
}

@Composable
fun ContactDetailScreen(vm: ContactDetailViewModel = hiltViewModel()) {
    val s by vm.state.collectAsStateWithLifecycle()
    if (s.loading) { Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { CircularProgressIndicator() }; return }
    val c = s.contact
    LazyColumn(Modifier.fillMaxSize().padding(horizontal = 12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        item {
            Card(Modifier.fillMaxWidth().padding(top = 12.dp)) {
                Column(Modifier.padding(16.dp)) {
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                        Text(c?.name ?: "Contact", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
                        Text(if (c?.isFavorite == true) "★" else "☆", modifier = Modifier.clickable { vm.toggleFavorite() })
                    }
                    c?.jobTitle?.let { Text(it, style = MaterialTheme.typography.bodyMedium) }
                    c?.phone?.let { Text(it, style = MaterialTheme.typography.bodyMedium) }
                    c?.email?.let { Text(it, style = MaterialTheme.typography.bodyMedium) }
                    if (!c?.tags.isNullOrEmpty()) Text("Tags: ${c!!.tags.joinToString(", ")}",
                        style = MaterialTheme.typography.labelMedium, modifier = Modifier.padding(top = 6.dp))
                }
            }
        }
        item { Text("Timeline", style = MaterialTheme.typography.titleMedium, modifier = Modifier.padding(top = 8.dp, bottom = 2.dp)) }
        if (s.offline) item { Text("Timeline unavailable offline", color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.labelMedium) }
        if (s.timeline.isEmpty() && !s.offline) item { Text("No activity yet", style = MaterialTheme.typography.bodySmall) }
        items(s.timeline, key = { it.id }) { e ->
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(12.dp)) {
                    Text(e.title, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Medium)
                    e.description?.takeIf { it.isNotBlank() }?.let { Text(it, style = MaterialTheme.typography.bodySmall, maxLines = 3) }
                    e.timestampMillis?.let { Text(Date(it).toString(), style = MaterialTheme.typography.labelSmall) }
                }
            }
        }
    }
}
