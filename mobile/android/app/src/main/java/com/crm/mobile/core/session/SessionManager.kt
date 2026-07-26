package com.crm.mobile.core.session

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import javax.inject.Inject
import javax.inject.Singleton

private val Context.dataStore by preferencesDataStore(name = "crm_session")

/**
 * Holds the JWT access + refresh tokens. Backed by DataStore; for production the
 * store file should sit behind the app's encrypted storage (SQLCipher / EncryptedFile)
 * and the refresh token gated by biometric unlock (see BiometricAuthenticator).
 */
@Singleton
class SessionManager @Inject constructor(
    @ApplicationContext private val context: Context,
) {
    private object Keys {
        val ACCESS = stringPreferencesKey("access_token")
        val REFRESH = stringPreferencesKey("refresh_token")
        val ROLE = stringPreferencesKey("user_role")
        val PUSH = stringPreferencesKey("push_token")
        val TEL_KEY = stringPreferencesKey("telephony_api_key")
        val TEL_SRN = stringPreferencesKey("telephony_srn")
        val TEL_PHONE = stringPreferencesKey("telephony_agent_phone")
    }

    val isLoggedIn: Flow<Boolean> =
        context.dataStore.data.map { !it[Keys.ACCESS].isNullOrBlank() }

    /** Cached role (SuperAdmin|OrgAdmin|Manager|Employee) for role-gated UI. */
    val role: Flow<String?> = context.dataStore.data.map { it[Keys.ROLE] }

    suspend fun accessToken(): String? = context.dataStore.data.first()[Keys.ACCESS]
    suspend fun refreshToken(): String? = context.dataStore.data.first()[Keys.REFRESH]
    suspend fun saveRole(role: String) { context.dataStore.edit { it[Keys.ROLE] = role } }

    // Native push (FCM) device token — registered after login, unregistered on logout.
    suspend fun pushToken(): String? = context.dataStore.data.first()[Keys.PUSH]
    suspend fun savePushToken(token: String) { context.dataStore.edit { it[Keys.PUSH] = token } }
    suspend fun clearPushToken() { context.dataStore.edit { it.remove(Keys.PUSH) } }

    suspend fun save(access: String, refresh: String) {
        context.dataStore.edit {
            it[Keys.ACCESS] = access
            it[Keys.REFRESH] = refresh
        }
    }

    suspend fun clear() {
        context.dataStore.edit { it.clear() }
    }

    // Telephony creds for server-side click-to-call (set in Settings). Empty
    // until configured — the backend then reports "calling not configured".
    suspend fun telephony(): TelephonyCreds {
        val p = context.dataStore.data.first()
        return TelephonyCreds(p[Keys.TEL_KEY], p[Keys.TEL_SRN], p[Keys.TEL_PHONE])
    }

    suspend fun saveTelephony(apiKey: String?, srn: String?, agentPhone: String?) {
        context.dataStore.edit {
            apiKey?.let { v -> it[Keys.TEL_KEY] = v }
            srn?.let { v -> it[Keys.TEL_SRN] = v }
            agentPhone?.let { v -> it[Keys.TEL_PHONE] = v }
        }
    }
}

data class TelephonyCreds(val apiKey: String?, val srn: String?, val agentPhone: String?) {
    val isConfigured: Boolean get() = !apiKey.isNullOrBlank() && !agentPhone.isNullOrBlank()
}
