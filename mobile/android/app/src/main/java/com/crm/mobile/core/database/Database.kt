package com.crm.mobile.core.database

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase
import com.crm.mobile.feature.cockpit.PipelineStageDao
import com.crm.mobile.feature.cockpit.PipelineStageEntity
import com.crm.mobile.feature.dashboard.DashboardDao
import com.crm.mobile.feature.dashboard.DashboardSnapshotEntity
import com.crm.mobile.feature.leads.LeadDao
import com.crm.mobile.feature.leads.LeadEntity
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

@Database(
    entities = [LeadEntity::class, DashboardSnapshotEntity::class, PipelineStageEntity::class],
    version = 3,
    exportSchema = false,
)
abstract class AppDatabase : RoomDatabase() {
    abstract fun leadDao(): LeadDao
    abstract fun dashboardDao(): DashboardDao
    abstract fun pipelineStageDao(): PipelineStageDao
}

@Module
@InstallIn(SingletonComponent::class)
object DatabaseModule {

    @Provides @Singleton
    fun database(@ApplicationContext ctx: Context): AppDatabase =
        // For production, wrap with SQLCipher (SupportFactory) + a key from the
        // Keystore-backed EncryptedFile so the cache is encrypted at rest.
        Room.databaseBuilder(ctx, AppDatabase::class.java, "crm.db")
            .fallbackToDestructiveMigration()
            .build()

    @Provides
    fun leadDao(db: AppDatabase): LeadDao = db.leadDao()

    @Provides
    fun dashboardDao(db: AppDatabase): DashboardDao = db.dashboardDao()

    @Provides
    fun pipelineStageDao(db: AppDatabase): PipelineStageDao = db.pipelineStageDao()
}
