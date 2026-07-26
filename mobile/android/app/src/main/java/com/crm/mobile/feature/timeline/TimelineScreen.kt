package com.crm.mobile.feature.timeline

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
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
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

@HiltViewModel
class TimelineViewModel @Inject constructor(private val repo: TimelineRepository) : ViewModel() {
    private val _type = MutableStateFlow<String?>(null)
    val type: StateFlow<String?> = _type.asStateFlow()
    private val _loading = MutableStateFlow(true)
    val loading: StateFlow<Boolean> = _loading.asStateFlow()
    private val _offline = MutableStateFlow(false)
    val offline: StateFlow<Boolean> = _offline.asStateFlow()

    val types: StateFlow<List<String>> = repo.activities
        .map { acts -> acts.map { it.type }.distinct().sorted() }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())

    val visible: StateFlow<List<TimelineActivity>> =
        combine(repo.activities, _type) { list, t ->
            if (t == null) list else list.filter { it.type.equals(t, ignoreCase = true) }
        }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())

    init { refresh() }
    fun refresh() { _loading.value = true; viewModelScope.launch { _offline.value = !repo.refresh(); _loading.value = false } }
    fun selectType(t: String?) { _type.value = if (_type.value == t) null else t }
}

@Composable
fun TimelineScreen(vm: TimelineViewModel = hiltViewModel()) {
    val type by vm.type.collectAsStateWithLifecycle()
    val types by vm.types.collectAsStateWithLifecycle()
    val loading by vm.loading.collectAsStateWithLifecycle()
    val offline by vm.offline.collectAsStateWithLifecycle()
    val items by vm.visible.collectAsStateWithLifecycle()

    Column(Modifier.fillMaxSize().padding(horizontal = 12.dp)) {
        if (offline) Text("Offline — showing cached timeline", color = MaterialTheme.colorScheme.error,
            style = MaterialTheme.typography.labelMedium, modifier = Modifier.padding(vertical = 8.dp))
        Row(Modifier.fillMaxWidth().padding(vertical = 8.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            FilterChip(selected = type == null, onClick = { vm.selectType(null) }, label = { Text("All") })
            types.take(5).forEach { t ->
                FilterChip(selected = type == t, onClick = { vm.selectType(t) }, label = { Text(t) })
            }
        }
        when {
            loading && items.isEmpty() ->
                Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
            items.isEmpty() -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { Text("No activity yet") }
            else -> LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                items(items, key = { it.id }) { a -> TimelineRow(a) }
            }
        }
    }
}

@Composable
private fun TimelineRow(a: TimelineActivity) {
    Card(Modifier.fillMaxWidth()) {
        Row(Modifier.padding(14.dp).fillMaxWidth()) {
            Text(a.glyph, style = MaterialTheme.typography.titleMedium, modifier = Modifier.padding(end = 12.dp))
            Column(Modifier.fillMaxWidth()) {
                Text(a.subject, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Medium)
                a.description?.takeIf { it.isNotBlank() }?.let {
                    Text(it, style = MaterialTheme.typography.bodySmall, maxLines = 2)
                }
                val meta = listOfNotNull(
                    a.type,
                    a.direction,
                    a.disposition,
                    Date(a.createdMillis).toString(),
                ).joinToString(" · ")
                Text(meta, style = MaterialTheme.typography.labelSmall)
            }
        }
    }
}
