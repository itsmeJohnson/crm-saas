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
    }

    val isLoggedIn: Flow<Boolean> =
        context.dataStore.data.map { !it[Keys.ACCESS].isNullOrBlank() }

    suspend fun accessToken(): String? = context.dataStore.data.first()[Keys.ACCESS]
    suspend fun refreshToken(): String? = context.dataStore.data.first()[Keys.REFRESH]

    suspend fun save(access: String, refresh: String) {
        context.dataStore.edit {
            it[Keys.ACCESS] = access
            it[Keys.REFRESH] = refresh
        }
    }

    suspend fun clear() {
        context.dataStore.edit { it.clear() }
    }
}
