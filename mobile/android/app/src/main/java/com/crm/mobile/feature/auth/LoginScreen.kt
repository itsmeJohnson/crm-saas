package com.crm.mobile.feature.auth

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.ListItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class LoginUiState(
    val email: String = "",
    val password: String = "",
    val loading: Boolean = false,
    val error: String? = null,
    val loggedIn: Boolean = false,
)

@HiltViewModel
class LoginViewModel @Inject constructor(
    private val repo: AuthRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(LoginUiState())
    val state: StateFlow<LoginUiState> = _state.asStateFlow()

    fun onEmail(v: String) = _state.update { it.copy(email = v, error = null) }
    fun onPassword(v: String) = _state.update { it.copy(password = v, error = null) }

    fun submit() {
        val s = _state.value
        if (s.email.isBlank() || s.password.isBlank()) {
            _state.update { it.copy(error = "Enter your email and password.") }
            return
        }
        _state.update { it.copy(loading = true, error = null) }
        viewModelScope.launch {
            runCatching { repo.login(s.email, s.password) }
                .onSuccess { _state.update { st -> st.copy(loading = false, loggedIn = true) } }
                .onFailure { e ->
                    _state.update { st -> st.copy(loading = false, error = e.toUserMessage()) }
                }
        }
    }
}

private fun Throwable.toUserMessage(): String = when {
    message?.contains("401") == true -> "Incorrect email or password."
    message?.contains("Unable to resolve host") == true ||
        message?.contains("timeout") == true ||
        message?.contains("Connection refused") == true -> "Can't reach the server. Check your connection or host IP."
    else -> "Sign-in failed: ${message ?: "Unknown error"}"
}

@Composable
fun LoginScreen(
    onLoggedIn: () -> Unit,
    vm: LoginViewModel = hiltViewModel(),
) {
    val state by vm.state.collectAsStateWithLifecycle()

    LaunchedEffect(state.loggedIn) { if (state.loggedIn) onLoggedIn() }

    Column(
        modifier = Modifier.fillMaxSize().padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Spacer(Modifier.height(48.dp))
        Text("Enterprise CRM", style = MaterialTheme.typography.headlineMedium)
        Text("Sign in to continue", style = MaterialTheme.typography.bodyMedium)

        OutlinedTextField(
            value = state.email,
            onValueChange = vm::onEmail,
            label = { Text("Email") },
            singleLine = true,
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email),
            modifier = Modifier.fillMaxWidth().padding(top = 24.dp),
        )
        OutlinedTextField(
            value = state.password,
            onValueChange = vm::onPassword,
            label = { Text("Password") },
            singleLine = true,
            visualTransformation = PasswordVisualTransformation(),
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
            modifier = Modifier.fillMaxWidth().padding(top = 12.dp),
        )

        state.error?.let {
            Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(top = 12.dp))
        }

        Button(
            onClick = vm::submit,
            enabled = !state.loading,
            modifier = Modifier.fillMaxWidth().padding(top = 20.dp),
        ) {
            if (state.loading) CircularProgressIndicator(modifier = Modifier.padding(end = 8.dp))
            Text("Sign in")
        }

        Spacer(Modifier.height(32.dp))
        HorizontalDivider()
        Spacer(Modifier.height(16.dp))

        Text(
            "Quick Demo Login",
            style = MaterialTheme.typography.titleSmall,
            modifier = Modifier.align(Alignment.Start)
        )

        val demoUsers = listOf(
            DemoUser("Director / Owner", "admin@professional-demo.com"),
            DemoUser("Sales Manager", "karan.singh@professional-demo.demo"),
            DemoUser("Sales Executive (Amit)", "amit.kumar@professional-demo.demo"),
            DemoUser("Sales Executive (Divya)", "divya.nair@professional-demo.demo"),
            DemoUser("Sales Executive (Meena)", "meena.joshi@professional-demo.demo"),
        )

        LazyColumn(
            modifier = Modifier.fillMaxWidth().weight(1f)
        ) {
            items(demoUsers) { user ->
                ListItem(
                    headlineContent = { Text(user.role, fontWeight = FontWeight.Bold) },
                    supportingContent = { Text(user.email) },
                    modifier = Modifier.clickable {
                        vm.onEmail(user.email)
                        vm.onPassword("Demo@12345")
                    }
                )
            }
        }
    }
}

private data class DemoUser(val role: String, val email: String)
