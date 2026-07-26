package com.crm.mobile.feature.leads

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
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
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class LeadsViewModel @Inject constructor(
    private val repo: LeadRepository,
) : ViewModel() {

    // The list is driven by the local cache — always available, even offline.
    val leads: StateFlow<List<Lead>> = repo.leads
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())

    private val _offline = MutableStateFlow(false)
    val offline: StateFlow<Boolean> = _offline.asStateFlow()

    init { refresh() }

    fun refresh() {
        viewModelScope.launch { _offline.value = !repo.refresh() }
    }
}

@Composable
fun LeadsScreen(vm: LeadsViewModel = hiltViewModel()) {
    val leads by vm.leads.collectAsStateWithLifecycle()
    val offline by vm.offline.collectAsStateWithLifecycle()

    Column(modifier = Modifier.fillMaxSize()) {
        if (offline) {
            Text(
                "Offline — showing cached leads",
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.error,
                modifier = Modifier.padding(16.dp),
            )
        }
        LazyColumn(modifier = Modifier.fillMaxSize().padding(horizontal = 12.dp)) {
            items(leads, key = { it.id }) { lead -> LeadRow(lead) }
        }
    }
}

@Composable
private fun LeadRow(lead: Lead) {
    Card(modifier = Modifier.fillMaxWidth().padding(vertical = 6.dp)) {
        Column(modifier = Modifier.padding(14.dp)) {
            Text(lead.title, style = MaterialTheme.typography.titleMedium)
            Text(
                "${lead.name} · ${lead.status} · ${lead.priority}",
                style = MaterialTheme.typography.bodySmall,
            )
            lead.phone?.let { Text(it, style = MaterialTheme.typography.bodySmall) }
        }
    }
}
