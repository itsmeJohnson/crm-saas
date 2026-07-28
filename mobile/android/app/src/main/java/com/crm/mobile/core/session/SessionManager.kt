package com.crm.mobile.core.session

import android.content.Context
import androidx.datastore.preferences.core.MutablePreferences
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.booleanPreferencesKey
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
        val TEL_PROVIDER = stringPreferencesKey("telephony_provider")
        val TEL_KEY = stringPreferencesKey("telephony_api_key")
        val TEL_SRN = stringPreferencesKey("telephony_srn")
        val TEL_PHONE = stringPreferencesKey("telephony_agent_phone")
        val TEL_MYOP_KEY = stringPreferencesKey("telephony_myop_x_api_key")
        val TEL_MYOP_SECRET = stringPreferencesKey("telephony_myop_secret_key")
        val TEL_MYOP_COMPANY = stringPreferencesKey("telephony_myop_company_id")
        val TEL_MYOP_CALLER = stringPreferencesKey("telephony_myop_caller_id")
        val BIOMETRIC = booleanPreferencesKey("biometric_enabled")
        val PUSH_ENABLED = booleanPreferencesKey("push_enabled")
    }

    /** Biometric app-unlock preference (default off until the user opts in). */
    val biometricEnabled: Flow<Boolean> = context.dataStore.data.map { it[Keys.BIOMETRIC] ?: false }
    suspend fun setBiometricEnabled(on: Boolean) { context.dataStore.edit { it[Keys.BIOMETRIC] = on } }

    /** Native-push opt-in (default on; toggled from Profile settings). */
    val pushEnabled: Flow<Boolean> = context.dataStore.data.map { it[Keys.PUSH_ENABLED] ?: true }
    suspend fun setPushEnabled(on: Boolean) { context.dataStore.edit { it[Keys.PUSH_ENABLED] = on } }

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
    // `provider` selects the gateway (knowlarity | myoperator); only that
    // provider's fields are used by the backend dialer.
    suspend fun telephony(): TelephonyCreds {
        val p = context.dataStore.data.first()
        return TelephonyCreds(
            provider = p[Keys.TEL_PROVIDER] ?: "knowlarity",
            apiKey = p[Keys.TEL_KEY],
            srn = p[Keys.TEL_SRN],
            agentPhone = p[Keys.TEL_PHONE],
            myopXApiKey = p[Keys.TEL_MYOP_KEY],
            myopSecretKey = p[Keys.TEL_MYOP_SECRET],
            myopCompanyId = p[Keys.TEL_MYOP_COMPANY],
            myopCallerId = p[Keys.TEL_MYOP_CALLER],
        )
    }

    /** Persists the full telephony config. Blank values are removed so switching
     *  provider / clearing a field actually takes effect. */
    suspend fun saveTelephony(creds: TelephonyCreds) {
        context.dataStore.edit { p ->
            p[Keys.TEL_PROVIDER] = creds.provider
            p.putOrRemove(Keys.TEL_PHONE, creds.agentPhone)
            p.putOrRemove(Keys.TEL_KEY, creds.apiKey)
            p.putOrRemove(Keys.TEL_SRN, creds.srn)
            p.putOrRemove(Keys.TEL_MYOP_KEY, creds.myopXApiKey)
            p.putOrRemove(Keys.TEL_MYOP_SECRET, creds.myopSecretKey)
            p.putOrRemove(Keys.TEL_MYOP_COMPANY, creds.myopCompanyId)
            p.putOrRemove(Keys.TEL_MYOP_CALLER, creds.myopCallerId)
        }
    }

    private fun MutablePreferences.putOrRemove(key: Preferences.Key<String>, value: String?) {
        if (value.isNullOrBlank()) remove(key) else set(key, value)
    }
}

data class TelephonyCreds(
    val provider: String = "knowlarity",
    val apiKey: String? = null,
    val srn: String? = null,
    val agentPhone: String? = null,
    val myopXApiKey: String? = null,
    val myopSecretKey: String? = null,
    val myopCompanyId: String? = null,
    val myopCallerId: String? = null,
) {
    val isConfigured: Boolean
        get() = if (provider == "myoperator") {
            !agentPhone.isNullOrBlank() && !myopXApiKey.isNullOrBlank() &&
                !myopSecretKey.isNullOrBlank() && !myopCompanyId.isNullOrBlank()
        } else {
            !apiKey.isNullOrBlank() && !agentPhone.isNullOrBlank()
        }
}
