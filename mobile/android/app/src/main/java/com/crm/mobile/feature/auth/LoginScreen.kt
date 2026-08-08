package com.crm.mobile.feature.auth

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.crm.mobile.core.design.DentalColors
import com.crm.mobile.core.session.SessionManager
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class LoginUiState(
    val email: String = "dr.arvind@smilecaredental.com",
    val password: String = "Demo@12345",
    val serverUrl: String = "http://192.168.1.6:8000",
    val showServerConfig: Boolean = false,
    val loading: Boolean = false,
    val error: String? = null,
    val loggedIn: Boolean = false,
)

@HiltViewModel
class LoginViewModel @Inject constructor(
    private val repo: AuthRepository,
    private val session: SessionManager,
) : ViewModel() {

    private val _state = MutableStateFlow(LoginUiState())
    val state: StateFlow<LoginUiState> = _state.asStateFlow()

    init {
        viewModelScope.launch {
            val savedUrl = session.getServerUrl()
            if (!savedUrl.isNullOrBlank()) {
                _state.update { it.copy(serverUrl = savedUrl) }
            }
        }
    }

    fun onEmail(v: String) = _state.update { it.copy(email = v, error = null) }
    fun onPassword(v: String) = _state.update { it.copy(password = v, error = null) }
    fun onServerUrl(v: String) = _state.update { it.copy(serverUrl = v) }
    fun toggleServerConfig() = _state.update { it.copy(showServerConfig = !it.showServerConfig) }

    fun saveServerUrl() {
        viewModelScope.launch {
            session.setServerUrl(_state.value.serverUrl)
            _state.update { it.copy(showServerConfig = false) }
        }
    }

    fun submit() {
        val s = _state.value
        if (s.email.isBlank() || s.password.isBlank()) {
            _state.update { it.copy(error = "Enter your clinic email and password.") }
            return
        }
        _state.update { it.copy(loading = true, error = null) }
        viewModelScope.launch {
            session.setServerUrl(s.serverUrl)
            runCatching { repo.login(s.email, s.password) }
                .onSuccess { _state.update { st -> st.copy(loading = false, loggedIn = true) } }
                .onFailure { e ->
                    _state.update { st -> st.copy(loading = false, error = e.toUserMessage(s.serverUrl)) }
                }
        }
    }

    fun bypassLogin() {
        _state.update { it.copy(loggedIn = true) }
    }
}

private fun Throwable.toUserMessage(serverUrl: String): String = when {
    message?.contains("401") == true -> "Incorrect email or password."
    message?.contains("Unable to resolve host") == true ||
        message?.contains("timeout") == true ||
        message?.contains("Connection refused") == true ||
        message?.contains("Failed to connect") == true -> "Unable to reach server at $serverUrl. Check IP / VPS host or tap ⚙ to change."
    else -> "Sign-in error: ${message ?: "Unknown error"}"
}

@Composable
fun LoginScreen(
    onLoggedIn: () -> Unit,
    vm: LoginViewModel = hiltViewModel(),
) {
    val state by vm.state.collectAsStateWithLifecycle()

    LaunchedEffect(state.loggedIn) { if (state.loggedIn) onLoggedIn() }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background)
            .padding(horizontal = 24.dp, vertical = 20.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.End
        ) {
            IconButton(onClick = vm::toggleServerConfig) {
                Text("⚙️", fontSize = 18.sp)
            }
        }

        // Dental Logo & Title
        Box(
            modifier = Modifier
                .size(54.dp)
                .clip(RoundedCornerShape(14.dp))
                .background(DentalColors.Teal600),
            contentAlignment = Alignment.Center
        ) {
            Text("🦷", fontSize = 28.sp)
        }
        Spacer(Modifier.height(10.dp))
        Text(
            "FewClick CRM",
            style = MaterialTheme.typography.headlineMedium,
            fontWeight = FontWeight.Bold,
            color = MaterialTheme.colorScheme.onBackground
        )
        Text(
            "Dental Clinic & Practice Portal",
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )

        // VPS / Server URL Configuration Box
        if (state.showServerConfig) {
            Card(
                modifier = Modifier.fillMaxWidth().padding(top = 14.dp),
                shape = RoundedCornerShape(12.dp),
                colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.5f))
            ) {
                Column(modifier = Modifier.padding(12.dp)) {
                    Text("Backend Server / VPS URL", fontWeight = FontWeight.Bold, style = MaterialTheme.typography.labelMedium)
                    OutlinedTextField(
                        value = state.serverUrl,
                        onValueChange = vm::onServerUrl,
                        singleLine = true,
                        shape = RoundedCornerShape(8.dp),
                        modifier = Modifier.fillMaxWidth().padding(top = 6.dp)
                    )
                    Row(
                        modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
                        horizontalArrangement = Arrangement.End
                    ) {
                        TextButton(onClick = vm::saveServerUrl) {
                            Text("Save Server URL", color = DentalColors.Teal700, fontWeight = FontWeight.Bold)
                        }
                    }
                }
            }
        }

        OutlinedTextField(
            value = state.email,
            onValueChange = vm::onEmail,
            label = { Text("Clinic Staff Email") },
            singleLine = true,
            shape = RoundedCornerShape(12.dp),
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email),
            modifier = Modifier.fillMaxWidth().padding(top = 14.dp),
        )
        OutlinedTextField(
            value = state.password,
            onValueChange = vm::onPassword,
            label = { Text("Password") },
            singleLine = true,
            shape = RoundedCornerShape(12.dp),
            visualTransformation = PasswordVisualTransformation(),
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
            modifier = Modifier.fillMaxWidth().padding(top = 10.dp),
        )

        state.error?.let {
            Text(
                it,
                color = MaterialTheme.colorScheme.error,
                style = MaterialTheme.typography.bodySmall,
                modifier = Modifier.padding(top = 10.dp)
            )
        }

        Button(
            onClick = vm::submit,
            enabled = !state.loading,
            shape = RoundedCornerShape(12.dp),
            colors = ButtonDefaults.buttonColors(containerColor = DentalColors.Teal600),
            modifier = Modifier.fillMaxWidth().padding(top = 14.dp),
        ) {
            if (state.loading) CircularProgressIndicator(modifier = Modifier.size(18.dp).padding(end = 8.dp), color = Color.White)
            Text("Sign in to Practice", fontWeight = FontWeight.Bold, style = MaterialTheme.typography.labelLarge)
        }

        // Instant 1-Click Practice Demo Button
        OutlinedButton(
            onClick = vm::bypassLogin,
            shape = RoundedCornerShape(12.dp),
            border = androidx.compose.foundation.BorderStroke(1.dp, DentalColors.Teal600),
            modifier = Modifier.fillMaxWidth().padding(top = 10.dp),
        ) {
            Text("⚡ Open Demo Practice (FewClick Mode)", color = DentalColors.Teal700, fontWeight = FontWeight.Bold, style = MaterialTheme.typography.labelMedium)
        }

        Spacer(Modifier.height(14.dp))
        HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.5f))
        Spacer(Modifier.height(10.dp))

        Text(
            "Quick Dental Staff Accounts",
            style = MaterialTheme.typography.titleSmall,
            fontWeight = FontWeight.Bold,
            color = MaterialTheme.colorScheme.onSurface,
            modifier = Modifier.align(Alignment.Start)
        )

        val dentalDemoUsers = listOf(
            DemoUser("Lead Dentist / Owner", "dr.arvind@smilecaredental.com", "Dr. Arvind Mehta"),
            DemoUser("Specialist Endodontist", "dr.priya@smilecaredental.com", "Dr. Priya Sharma"),
            DemoUser("Cosmetic & Oral Surgeon", "dr.vikram@smilecaredental.com", "Dr. Vikram Rao"),
            DemoUser("Clinic Receptionist", "sneha.reception@smilecaredental.com", "Sneha Patel"),
        )

        LazyColumn(
            modifier = Modifier.fillMaxWidth().weight(1f),
            verticalArrangement = Arrangement.spacedBy(6.dp)
        ) {
            items(dentalDemoUsers) { user ->
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clickable {
                            vm.onEmail(user.email)
                            vm.onPassword("Demo@12345")
                        },
                    shape = RoundedCornerShape(10.dp),
                    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
                    border = CardDefaults.outlinedCardBorder().copy(
                        brush = androidx.compose.ui.graphics.SolidColor(MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.5f))
                    )
                ) {
                    Row(
                        modifier = Modifier.padding(horizontal = 12.dp, vertical = 10.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Box(
                            modifier = Modifier
                                .size(32.dp)
                                .clip(CircleShape)
                                .background(DentalColors.Teal100),
                            contentAlignment = Alignment.Center
                        ) {
                            Text("🩺", fontSize = 14.sp)
                        }
                        Spacer(modifier = Modifier.width(10.dp))
                        Column {
                            Text(user.role, fontWeight = FontWeight.Bold, style = MaterialTheme.typography.titleSmall.copy(fontSize = 13.sp))
                            Text("${user.name} • ${user.email}", style = MaterialTheme.typography.bodySmall.copy(fontSize = 11.sp), color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                }
            }
        }
    }
}

private data class DemoUser(val role: String, val email: String, val name: String)
