package com.crm.mobile.feature.customers

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
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import java.util.Date
import javax.inject.Inject

private fun money(v: Double): String = "₹" + String.format("%,.0f", v)

// ---------- List ----------

@HiltViewModel
class CustomersViewModel @Inject constructor(private val repo: CustomerRepository) : ViewModel() {
    private val _query = MutableStateFlow("")
    val query: StateFlow<String> = _query.asStateFlow()
    private val _loading = MutableStateFlow(true)
    val loading: StateFlow<Boolean> = _loading.asStateFlow()
    private val _offline = MutableStateFlow(false)
    val offline: StateFlow<Boolean> = _offline.asStateFlow()

    val visible: StateFlow<List<Customer>> = combine(repo.customers, _query) { list, q ->
        if (q.isBlank()) list else list.filter { it.name.contains(q, ignoreCase = true) }
    }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())

    init { refresh() }
    fun refresh() {
        _loading.value = true
        viewModelScope.launch { _offline.value = !repo.refresh(); _loading.value = false }
    }
    fun setQuery(q: String) { _query.value = q }
}

@Composable
fun CustomersListScreen(onOpen: (String) -> Unit, vm: CustomersViewModel = hiltViewModel()) {
    val query by vm.query.collectAsStateWithLifecycle()
    val loading by vm.loading.collectAsStateWithLifecycle()
    val offline by vm.offline.collectAsStateWithLifecycle()
    val customers by vm.visible.collectAsStateWithLifecycle()

    Column(Modifier.fillMaxSize().padding(horizontal = 12.dp)) {
        if (offline) Text("Offline — showing cached customers", color = MaterialTheme.colorScheme.error,
            style = MaterialTheme.typography.labelMedium, modifier = Modifier.padding(vertical = 8.dp))
        OutlinedTextField(query, vm::setQuery, label = { Text("Search customers") }, singleLine = true,
            modifier = Modifier.fillMaxWidth().padding(top = 8.dp))
        when {
            loading && customers.isEmpty() ->
                Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
            customers.isEmpty() ->
                Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { Text("No customers") }
            else -> LazyColumn(Modifier.padding(top = 8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                items(customers, key = { it.companyId }) { c ->
                    Card(Modifier.fillMaxWidth().clickable { onOpen(c.companyId) }) {
                        Column(Modifier.padding(14.dp)) {
                            Text(c.name, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Medium)
                            c.industry?.let { Text(it, style = MaterialTheme.typography.bodySmall) }
                            Text("${c.orderCount} orders · outstanding ${money(c.outstandingBalance)}",
                                style = MaterialTheme.typography.labelMedium)
                        }
                    }
                }
            }
        }
    }
}

// ---------- Detail (profile header + unified timeline) ----------

data class CustomerDetailState(
    val loading: Boolean = true,
    val offline: Boolean = false,
    val customer: Customer? = null,
    val timeline: List<TimelineEvent> = emptyList(),
)

@HiltViewModel
class CustomerDetailViewModel @Inject constructor(
    savedStateHandle: SavedStateHandle,
    private val repo: CustomerRepository,
) : ViewModel() {
    private val companyId: String = savedStateHandle["companyId"] ?: ""
    private val _state = MutableStateFlow(CustomerDetailState())
    val state: StateFlow<CustomerDetailState> = _state.asStateFlow()

    init {
        viewModelScope.launch {
            val header = repo.customer(companyId)
            repo.timeline(companyId)
                .onSuccess { _state.value = CustomerDetailState(false, false, header, it) }
                .onFailure { _state.value = CustomerDetailState(false, true, header, emptyList()) }
        }
    }
}

@Composable
fun CustomerDetailScreen(vm: CustomerDetailViewModel = hiltViewModel()) {
    val s by vm.state.collectAsStateWithLifecycle()

    if (s.loading) {
        Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
        return
    }
    LazyColumn(Modifier.fillMaxSize().padding(horizontal = 12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        item {
            Card(Modifier.fillMaxWidth().padding(top = 12.dp)) {
                Column(Modifier.padding(16.dp)) {
                    Text(s.customer?.name ?: "Customer", style = MaterialTheme.typography.headlineSmall,
                        fontWeight = FontWeight.Bold)
                    s.customer?.industry?.let { Text(it, style = MaterialTheme.typography.bodyMedium) }
                    s.customer?.let {
                        Text("Invoiced ${money(it.totalInvoiced)} · outstanding ${money(it.outstandingBalance)}",
                            style = MaterialTheme.typography.bodyMedium, modifier = Modifier.padding(top = 6.dp))
                    }
                }
            }
        }
        item {
            Text("Timeline", style = MaterialTheme.typography.titleMedium,
                modifier = Modifier.padding(top = 8.dp, bottom = 2.dp))
        }
        if (s.offline) item { Text("Timeline unavailable offline", color = MaterialTheme.colorScheme.error,
            style = MaterialTheme.typography.labelMedium) }
        if (s.timeline.isEmpty() && !s.offline) item { Text("No activity yet", style = MaterialTheme.typography.bodySmall) }
        items(s.timeline, key = { it.id }) { e -> TimelineRow(e) }
    }
}

@Composable
private fun TimelineRow(e: TimelineEvent) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(12.dp)) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text(e.title, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Medium)
                Text(e.group, style = MaterialTheme.typography.labelSmall)
            }
            e.description?.takeIf { it.isNotBlank() }?.let {
                Text(it, style = MaterialTheme.typography.bodySmall, maxLines = 3)
            }
            val meta = listOfNotNull(e.actorName, e.timestampMillis?.let { Date(it).toString() }).joinToString(" · ")
            if (meta.isNotBlank()) Text(meta, style = MaterialTheme.typography.labelSmall)
        }
    }
}
