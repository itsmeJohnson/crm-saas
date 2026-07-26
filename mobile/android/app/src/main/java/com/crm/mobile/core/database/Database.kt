package com.crm.mobile.core.database

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase
import com.crm.mobile.feature.calendar.CalendarDao
import com.crm.mobile.feature.calendar.CalendarItemEntity
import com.crm.mobile.feature.cockpit.PipelineStageDao
import com.crm.mobile.feature.cockpit.PipelineStageEntity
import com.crm.mobile.feature.contacts.ContactDao
import com.crm.mobile.feature.contacts.ContactEntity
import com.crm.mobile.feature.contacts.ContactFavoriteEntity
import com.crm.mobile.feature.customers.CustomerDao
import com.crm.mobile.feature.customers.CustomerEntity
import com.crm.mobile.feature.dashboard.DashboardDao
import com.crm.mobile.feature.dashboard.DashboardSnapshotEntity
import com.crm.mobile.feature.leads.LeadDao
import com.crm.mobile.feature.leads.LeadEntity
import com.crm.mobile.feature.reminders.ReminderDao
import com.crm.mobile.feature.reminders.ReminderEntity
import com.crm.mobile.feature.timeline.ActivityDao
import com.crm.mobile.feature.timeline.ActivityEntity
import com.crm.mobile.feature.tasks.TaskDao
import com.crm.mobile.feature.tasks.TaskEntity
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

@Database(
    entities = [
        LeadEntity::class, DashboardSnapshotEntity::class,
        PipelineStageEntity::class, TaskEntity::class, CalendarItemEntity::class,
        CustomerEntity::class, ContactEntity::class, ContactFavoriteEntity::class,
        ActivityEntity::class, ReminderEntity::class,
    ],
    version = 9,
    exportSchema = false,
)
abstract class AppDatabase : RoomDatabase() {
    abstract fun leadDao(): LeadDao
    abstract fun dashboardDao(): DashboardDao
    abstract fun pipelineStageDao(): PipelineStageDao
    abstract fun taskDao(): TaskDao
    abstract fun calendarDao(): CalendarDao
    abstract fun customerDao(): CustomerDao
    abstract fun contactDao(): ContactDao
    abstract fun activityDao(): ActivityDao
    abstract fun reminderDao(): ReminderDao
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

    @Provides
    fun taskDao(db: AppDatabase): TaskDao = db.taskDao()

    @Provides
    fun calendarDao(db: AppDatabase): CalendarDao = db.calendarDao()

    @Provides
    fun customerDao(db: AppDatabase): CustomerDao = db.customerDao()

    @Provides
    fun contactDao(db: AppDatabase): ContactDao = db.contactDao()

    @Provides
    fun activityDao(db: AppDatabase): ActivityDao = db.activityDao()

    @Provides
    fun reminderDao(db: AppDatabase): ReminderDao = db.reminderDao()
}
