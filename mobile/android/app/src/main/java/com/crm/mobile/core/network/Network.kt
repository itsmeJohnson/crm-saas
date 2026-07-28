package com.crm.mobile.core.network

import com.crm.mobile.BuildConfig
import com.crm.mobile.core.session.SessionManager
import com.crm.mobile.feature.auth.AuthApi
import com.crm.mobile.feature.auth.RefreshRequest
import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import kotlinx.coroutines.runBlocking
import okhttp3.Authenticator
import okhttp3.Interceptor
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.Route
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.moshi.MoshiConverterFactory
import java.util.concurrent.TimeUnit
import javax.inject.Named
import javax.inject.Singleton

/**
 * Adds the bearer token to every request except the auth endpoints (which must
 * stay unauthenticated to avoid a refresh loop).
 */
class AuthInterceptor(private val session: SessionManager) : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val request = chain.request()
        if (request.url.encodedPath.contains("/auth/")) return chain.proceed(request)
        val token = runBlocking { session.accessToken() }
        val authed = if (token.isNullOrBlank()) request
        else request.newBuilder().header("Authorization", "Bearer $token").build()
        return chain.proceed(authed)
    }
}

/**
 * On a 401, transparently refreshes the access token once and retries. Uses a
 * dedicated no-auth AuthApi so it can't recurse through this authenticator.
 * Synchronized so concurrent 401s refresh only once.
 */
class TokenAuthenticator(
    private val session: SessionManager,
    private val refreshApi: AuthApi,
) : Authenticator {
    override fun authenticate(route: Route?, response: Response): Request? {
        if (responseCount(response) >= 2) return null // already retried
        synchronized(this) {
            val current = runBlocking { session.accessToken() }
            val failed = response.request.header("Authorization")?.removePrefix("Bearer ")
            // Someone else may have refreshed while we waited.
            if (current != null && current != failed) {
                return response.request.newBuilder()
                    .header("Authorization", "Bearer $current").build()
            }
            val refresh = runBlocking { session.refreshToken() } ?: return null
            val new = runCatching { runBlocking { refreshApi.refresh(RefreshRequest(refresh)) } }
                .getOrNull() ?: run { runBlocking { session.clear() }; return null }
            runBlocking { session.save(new.access_token, new.refresh_token ?: refresh) }
            return response.request.newBuilder()
                .header("Authorization", "Bearer ${new.access_token}").build()
        }
    }

    private fun responseCount(response: Response): Int {
        var r: Response? = response; var c = 1
        while (r?.priorResponse != null) { c++; r = r.priorResponse }
        return c
    }
}

@Module
@InstallIn(SingletonComponent::class)
object NetworkModule {

    @Provides @Singleton
    fun moshi(): Moshi = Moshi.Builder().add(KotlinJsonAdapterFactory()).build()

    /** Retrofit with NO authenticator — used only for token refresh. */
    @Provides @Singleton @Named("auth")
    fun authRetrofit(moshi: Moshi): Retrofit = Retrofit.Builder()
        .baseUrl("http://192.168.1.6:8000/api/v1/")
        .client(
            OkHttpClient.Builder()
                .connectTimeout(30, TimeUnit.SECONDS)
                .readTimeout(30, TimeUnit.SECONDS)
                .addLoggingInterceptor()
                .build()
        )
        .addConverterFactory(MoshiConverterFactory.create(moshi))
        .build()

    /** No-auth AuthApi, used ONLY by the token authenticator to avoid recursion. */
    @Provides @Singleton @Named("auth")
    fun refreshAuthApi(@Named("auth") retrofit: Retrofit): AuthApi = retrofit.create(AuthApi::class.java)

    @Provides @Singleton
    fun okHttp(session: SessionManager, @Named("auth") refreshApi: AuthApi): OkHttpClient =
        OkHttpClient.Builder()
            .connectTimeout(30, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS)
            .addInterceptor(AuthInterceptor(session))
            .authenticator(TokenAuthenticator(session, refreshApi))
            // Certificate pinning is enabled per-environment; add the backend's
            // SPKI pins here before production release:
            // .certificatePinner(CertificatePinner.Builder().add(host, "sha256/...").build())
            .addLoggingInterceptor()
            .build()

    @Provides @Singleton
    fun retrofit(client: OkHttpClient, moshi: Moshi): Retrofit = Retrofit.Builder()
        .baseUrl("http://192.168.1.6:8000/api/v1/")
        .client(client)
        .addConverterFactory(MoshiConverterFactory.create(moshi))
        .build()

    // ---- Feature APIs off the authenticated client ----

    @Provides @Singleton
    fun authApi(retrofit: Retrofit): AuthApi = retrofit.create(AuthApi::class.java)

    @Provides @Singleton
    fun leadApi(retrofit: Retrofit): com.crm.mobile.feature.leads.LeadApi =
        retrofit.create(com.crm.mobile.feature.leads.LeadApi::class.java)

    @Provides @Singleton
    fun dashboardApi(retrofit: Retrofit): com.crm.mobile.feature.dashboard.DashboardApi =
        retrofit.create(com.crm.mobile.feature.dashboard.DashboardApi::class.java)

    @Provides @Singleton
    fun cockpitApi(retrofit: Retrofit): com.crm.mobile.feature.cockpit.CockpitApi =
        retrofit.create(com.crm.mobile.feature.cockpit.CockpitApi::class.java)

    @Provides @Singleton
    fun taskApi(retrofit: Retrofit): com.crm.mobile.feature.tasks.TaskApi =
        retrofit.create(com.crm.mobile.feature.tasks.TaskApi::class.java)

    @Provides @Singleton
    fun calendarApi(retrofit: Retrofit): com.crm.mobile.feature.calendar.CalendarApi =
        retrofit.create(com.crm.mobile.feature.calendar.CalendarApi::class.java)

    @Provides @Singleton
    fun customerApi(retrofit: Retrofit): com.crm.mobile.feature.customers.CustomerApi =
        retrofit.create(com.crm.mobile.feature.customers.CustomerApi::class.java)

    @Provides @Singleton
    fun contactApi(retrofit: Retrofit): com.crm.mobile.feature.contacts.ContactApi =
        retrofit.create(com.crm.mobile.feature.contacts.ContactApi::class.java)

    @Provides @Singleton
    fun activityApi(retrofit: Retrofit): com.crm.mobile.feature.timeline.ActivityApi =
        retrofit.create(com.crm.mobile.feature.timeline.ActivityApi::class.java)

    @Provides @Singleton
    fun communicationApi(retrofit: Retrofit): com.crm.mobile.feature.communication.CommunicationApi =
        retrofit.create(com.crm.mobile.feature.communication.CommunicationApi::class.java)

    @Provides @Singleton
    fun reminderApi(retrofit: Retrofit): com.crm.mobile.feature.reminders.ReminderApi =
        retrofit.create(com.crm.mobile.feature.reminders.ReminderApi::class.java)

    @Provides @Singleton
    fun notificationApi(retrofit: Retrofit): com.crm.mobile.feature.notifications.NotificationApi =
        retrofit.create(com.crm.mobile.feature.notifications.NotificationApi::class.java)

    @Provides @Singleton
    fun deviceApi(retrofit: Retrofit): com.crm.mobile.core.push.DeviceApi =
        retrofit.create(com.crm.mobile.core.push.DeviceApi::class.java)

    @Provides @Singleton
    fun reportsApi(retrofit: Retrofit): com.crm.mobile.feature.reports.ReportsApi =
        retrofit.create(com.crm.mobile.feature.reports.ReportsApi::class.java)

    @Provides @Singleton
    fun profileApi(retrofit: Retrofit): com.crm.mobile.feature.profile.ProfileApi =
        retrofit.create(com.crm.mobile.feature.profile.ProfileApi::class.java)
}

private fun OkHttpClient.Builder.addLoggingInterceptor(): OkHttpClient.Builder {
    if (BuildConfig.DEBUG) {
        addInterceptor(HttpLoggingInterceptor().apply { level = HttpLoggingInterceptor.Level.BASIC })
    }
    return this
}
