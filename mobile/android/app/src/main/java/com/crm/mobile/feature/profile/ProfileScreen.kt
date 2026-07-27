package com.crm.mobile.feature.profile

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.fragment.app.FragmentActivity
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.crm.mobile.core.push.PushRegistrar
import com.crm.mobile.core.security.BiometricAuthenticator
import com.crm.mobile.core.session.SessionManager
import com.crm.mobile.core.session.TelephonyCreds
import com.crm.mobile.feature.auth.AuthRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import javax.inject.Inject

private val MANAGER_ROLES = setOf("SuperAdmin", "OrgAdmin", "Manager")

@HiltViewModel
class ProfileViewModel @Inject constructor(
    private val repo: ProfileRepository,
    private val auth: AuthRepository,
    private val session: SessionManager,
    private val push: PushRegistrar,
) : ViewModel() {
    private val _loading = MutableStateFlow(true)
    val loading: StateFlow<Boolean> = _loading.asStateFlow()
    private val _offline = MutableStateFlow(false)
    val offline: StateFlow<Boolean> = _offline.asStateFlow()
    private val _loggedOut = MutableStateFlow(false)
    val loggedOut: StateFlow<Boolean> = _loggedOut.asStateFlow()

    val bundle: StateFlow<ProfileBundle?> =
        repo.profile.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), null)
    val isManager: StateFlow<Boolean> = session.role.map { it in MANAGER_ROLES }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), false)
    val biometricEnabled: StateFlow<Boolean> =
        session.biometricEnabled.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), false)
    val pushEnabled: StateFlow<Boolean> =
        session.pushEnabled.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), true)
    val telephony = MutableStateFlow<TelephonyCreds?>(null)

    init {
        viewModelScope.launch { telephony.value = session.telephony() }
        refresh()
    }

    fun refresh() {
        _loading.value = true
        viewModelScope.launch {
            val mgr = session.role.first() in MANAGER_ROLES
            _offline.value = !repo.refresh(includeExpenses = mgr)
            _loading.value = false
        }
    }

    fun clockIn() = viewModelScope.launch { repo.clockIn(isManager.value) }
    fun clockOut() = viewModelScope.launch { repo.clockOut(isManager.value) }

    fun setBiometricEnabled(on: Boolean) = viewModelScope.launch { session.setBiometricEnabled(on) }

    fun setPushEnabled(on: Boolean) = viewModelScope.launch {
        session.setPushEnabled(on)
        if (on) push.registerAsync() else push.unregisterNow()
    }

    fun saveTelephony(apiKey: String, srn: String, phone: String) = viewModelScope.launch {
        session.saveTelephony(apiKey.ifBlank { null }, srn.ifBlank { null }, phone.ifBlank { null })
        telephony.value = session.telephony()
    }

    fun logout() = viewModelScope.launch { auth.logout(); _loggedOut.value = true }
}

@Composable
fun ProfileScreen(onLoggedOut: () -> Unit, vm: ProfileViewModel = hiltViewModel()) {
    val loading by vm.loading.collectAsStateWithLifecycle()
    val offline by vm.offline.collectAsStateWithLifecycle()
    val loggedOut by vm.loggedOut.collectAsStateWithLifecycle()
    val bundle by vm.bundle.collectAsStateWithLifecycle()
    val isManager by vm.isManager.collectAsStateWithLifecycle()
    val biometricOn by vm.biometricEnabled.collectAsStateWithLifecycle()
    val pushOn by vm.pushEnabled.collectAsStateWithLifecycle()
    val tel by vm.telephony.collectAsStateWithLifecycle()

    LaunchedEffect(loggedOut) { if (loggedOut) onLoggedOut() }

    when {
        loading && bundle == null ->
            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
        else -> Column(
            Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(12.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            if (offline) Text("Offline — showing cached profile", color = MaterialTheme.colorScheme.error,
                style = MaterialTheme.typography.labelMedium)

            ProfileHeader(bundle?.me)
            AttendanceCard(bundle, onClockIn = vm::clockIn, onClockOut = vm::clockOut)
            LeaveCard(bundle?.balances.orEmpty())
            if (isManager) ExpensesCard(bundle?.expenses.orEmpty())
            SettingsCard(
                biometricOn = biometricOn,
                pushOn = pushOn,
                tel = tel,
                onBiometric = vm::setBiometricEnabled,
                onPush = vm::setPushEnabled,
                onSaveTelephony = vm::saveTelephony,
                onLogout = vm::logout,
            )
        }
    }
}

@Composable
private fun ProfileHeader(me: ProfileMeDto?) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.fillMaxWidth().padding(16.dp)) {
            val name = me?.let { listOfNotNull(it.first_name, it.last_name).joinToString(" ").ifBlank { it.email } }
                ?: "—"
            Text(name, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.SemiBold)
            me?.email?.let { Text(it, style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant) }
            me?.role?.let { Text(it, style = MaterialTheme.typography.labelMedium) }
        }
    }
}

@Composable
private fun AttendanceCard(bundle: ProfileBundle?, onClockIn: () -> Unit, onClockOut: () -> Unit) {
    val att = bundle?.attendance
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("Attendance", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
            val r = att?.record
            Text(
                when {
                    r == null -> "Not clocked in today"
                    r.clock_out_at != null -> "Clocked out · ${r.worked_minutes} min worked"
                    else -> "Clocked in at ${r.clock_in_at ?: "—"}"
                },
                style = MaterialTheme.typography.bodyMedium,
            )
            val clockedIn = bundle?.isClockedIn == true
            if (clockedIn) OutlinedButton(onClick = onClockOut) { Text("Clock out") }
            else Button(onClick = onClockIn) { Text("Clock in") }
        }
    }
}

@Composable
private fun LeaveCard(balances: List<BalanceRowDto>) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("Leave balances", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
            if (balances.isEmpty()) {
                Text("No balances", style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
            } else balances.forEach { b ->
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                    Text(b.leave_type_name, style = MaterialTheme.typography.bodyMedium)
                    Text("${fmt(b.available)} / ${fmt(b.allocated)}", style = MaterialTheme.typography.bodyMedium)
                }
            }
        }
    }
}

@Composable
private fun ExpensesCard(expenses: List<ExpenseDto>) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("Expenses", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
            if (expenses.isEmpty()) {
                Text("No expenses", style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
            } else expenses.take(20).forEach { e ->
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                    Text(e.description?.ifBlank { e.category } ?: e.category,
                        style = MaterialTheme.typography.bodyMedium)
                    Text(fmt(e.amount), style = MaterialTheme.typography.bodyMedium)
                }
            }
        }
    }
}

@Composable
private fun SettingsCard(
    biometricOn: Boolean,
    pushOn: Boolean,
    tel: TelephonyCreds?,
    onBiometric: (Boolean) -> Unit,
    onPush: (Boolean) -> Unit,
    onSaveTelephony: (String, String, String) -> Unit,
    onLogout: () -> Unit,
) {
    val ctx = LocalContext.current
    val activity = ctx as? FragmentActivity
    val scope = rememberCoroutineScope()

    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Text("Settings & security", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)

            ToggleRow("Biometric unlock", biometricOn) { want ->
                if (want) {
                    val bio = activity?.let { BiometricAuthenticator(it) }
                    if (bio != null && bio.canAuthenticate()) {
                        scope.launch { if (bio.authenticate()) onBiometric(true) }
                    }
                } else onBiometric(false)
            }
            ToggleRow("Push notifications", pushOn, onPush)

            HorizontalDivider()
            Text("Click-to-call (telephony)", style = MaterialTheme.typography.labelLarge)

            var apiKey by remember(tel) { mutableStateOf(tel?.apiKey ?: "") }
            var srn by remember(tel) { mutableStateOf(tel?.srn ?: "") }
            var phone by remember(tel) { mutableStateOf(tel?.agentPhone ?: "") }
            OutlinedTextField(apiKey, { apiKey = it }, label = { Text("API key") }, singleLine = true,
                visualTransformation = PasswordVisualTransformation(), modifier = Modifier.fillMaxWidth())
            OutlinedTextField(srn, { srn = it }, label = { Text("SRN (optional)") }, singleLine = true,
                modifier = Modifier.fillMaxWidth())
            OutlinedTextField(phone, { phone = it }, label = { Text("Agent phone") }, singleLine = true,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Phone),
                modifier = Modifier.fillMaxWidth())
            OutlinedButton(onClick = { onSaveTelephony(apiKey, srn, phone) }) { Text("Save telephony") }

            HorizontalDivider()
            Button(onClick = onLogout, modifier = Modifier.fillMaxWidth()) { Text("Log out") }
        }
    }
}

@Composable
private fun ToggleRow(label: String, checked: Boolean, onChange: (Boolean) -> Unit) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically) {
        Text(label, style = MaterialTheme.typography.bodyMedium)
        Switch(checked = checked, onCheckedChange = onChange)
    }
}

private fun fmt(v: Double): String = if (v == v.toLong().toDouble()) v.toLong().toString() else v.toString()
