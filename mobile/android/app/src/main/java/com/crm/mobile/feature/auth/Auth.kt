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
data class UserDto(
    val id: String = "",
    val email: String = "",
    val first_name: String? = null,
    val last_name: String? = null,
    val role: String = "OrgAdmin",
    val organization_id: String? = null,
)

@JsonClass(generateAdapter = true)
data class OrganizationDto(
    val id: String? = null,
    val name: String? = null,
    val slug: String? = null,
)

@JsonClass(generateAdapter = true)
data class MeResponse(
    val user: UserDto? = null,
    val organization: OrganizationDto? = null,
    val features: List<String> = emptyList(),
    // Fallbacks if flat
    val id: String? = null,
    val email: String? = null,
    val first_name: String? = null,
    val last_name: String? = null,
    val role: String? = null,
    val organization_id: String? = null,
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
        try {
            pushRegistrar.registerAsync(Build.MODEL)  // best-effort native-push enrolment
        } catch (e: Exception) {
            // non-fatal
        }
        return user
    }

    suspend fun me(): CurrentUser {
        val m = api.me()
        val u = m.user
        val userId = u?.id?.ifBlank { null } ?: m.id ?: "usr-current"
        val firstName = u?.first_name ?: m.first_name
        val lastName = u?.last_name ?: m.last_name
        val userEmail = u?.email?.ifBlank { null } ?: m.email ?: "user@fewclick.crm"
        val userRole = u?.role?.ifBlank { null } ?: m.role ?: "OrgAdmin"
        val orgId = u?.organization_id ?: m.organization_id ?: m.organization?.id ?: ""

        return CurrentUser(
            id = userId,
            name = listOfNotNull(firstName, lastName).joinToString(" ").ifBlank { userEmail },
            role = userRole,
            organizationId = orgId,
        )
    }

    suspend fun logout() {
        try {
            pushRegistrar.unregisterNow()   // must run before the session (and token) is cleared
        } catch (e: Exception) {
            // ignore
        }
        session.clear()
    }
}
