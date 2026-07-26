package com.crm.mobile.feature.auth

import android.os.Build
import com.crm.mobile.core.push.PushRegistrar
import com.crm.mobile.core.session.SessionManager
import com.squareup.moshi.JsonClass
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import javax.inject.Inject
import javax.inject.Singleton

// ---- Wire DTOs (mirror the backend /auth contract) ----

@JsonClass(generateAdapter = true)
data class LoginRequest(val email: String, val password: String)

@JsonClass(generateAdapter = true)
data class RefreshRequest(val refresh_token: String)

@JsonClass(generateAdapter = true)
data class TokenResponse(val access_token: String, val refresh_token: String?)

@JsonClass(generateAdapter = true)
data class MeResponse(
    val id: String,
    val email: String,
    val first_name: String?,
    val last_name: String?,
    val role: String,
    val organization_id: String,
)

interface AuthApi {
    @POST("auth/login")
    suspend fun login(@Body body: LoginRequest): TokenResponse

    @POST("auth/refresh")
    suspend fun refresh(@Body body: RefreshRequest): TokenResponse

    @GET("auth/me")
    suspend fun me(): MeResponse
}

/** Domain model the UI works with. */
data class CurrentUser(
    val id: String,
    val name: String,
    val role: String,
    val organizationId: String,
)

@Singleton
class AuthRepository @Inject constructor(
    private val api: AuthApi,
    private val session: SessionManager,
    private val pushRegistrar: PushRegistrar,
) {
    /** Logs in and persists tokens. Returns the authenticated user. */
    suspend fun login(email: String, password: String): CurrentUser {
        val token = api.login(LoginRequest(email.trim(), password))
        session.save(token.access_token, token.refresh_token ?: "")
        val user = me()
        session.saveRole(user.role)   // cache role for role-gated navigation
        pushRegistrar.registerAsync(Build.MODEL)  // best-effort native-push enrolment
        return user
    }

    suspend fun me(): CurrentUser {
        val m = api.me()
        return CurrentUser(
            id = m.id,
            name = listOfNotNull(m.first_name, m.last_name).joinToString(" ").ifBlank { m.email },
            role = m.role,
            organizationId = m.organization_id,
        )
    }

    suspend fun logout() {
        pushRegistrar.unregisterNow()   // must run before the session (and token) is cleared
        session.clear()
    }
}
