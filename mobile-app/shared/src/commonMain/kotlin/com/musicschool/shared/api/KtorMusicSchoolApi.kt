package com.musicschool.shared.api

import com.musicschool.shared.model.AvailabilitySlot
import com.musicschool.shared.model.BookingSummary
import com.musicschool.shared.model.LoginRequest
import com.musicschool.shared.model.RoleRequest
import com.musicschool.shared.model.UserSummary
import io.ktor.client.HttpClient
import io.ktor.client.call.body
import io.ktor.client.plugins.contentnegotiation.ContentNegotiation
import io.ktor.client.request.get
import io.ktor.client.request.patch
import io.ktor.client.request.post
import io.ktor.client.request.setBody
import io.ktor.http.ContentType
import io.ktor.http.contentType
import io.ktor.serialization.kotlinx.json.json
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.int
import kotlinx.serialization.json.jsonPrimitive

class KtorMusicSchoolApi(
    private val baseUrl: String,
    private val httpClient: HttpClient = HttpClient {
        install(ContentNegotiation) {
            json(Json { ignoreUnknownKeys = true })
        }
    },
) : MusicSchoolApi {

    override suspend fun login(request: LoginRequest): UserSummary {
        val response: JsonObject = httpClient.post("$baseUrl/api/v1/auth/login") {
            contentType(ContentType.Application.Json)
            setBody(request)
        }.body()
        return Json.decodeFromJsonElement(UserSummary.serializer(), response["user"]!!)
    }

    override suspend fun me(): UserSummary {
        val response: JsonObject = httpClient.get("$baseUrl/api/v1/auth/me").body()
        return Json.decodeFromJsonElement(UserSummary.serializer(), response["user"]!!)
    }

    override suspend fun selectRole(request: RoleRequest) {
        httpClient.post("$baseUrl/api/v1/auth/select-role") {
            contentType(ContentType.Application.Json)
            setBody(request)
        }
    }

    override suspend fun studentAvailability(startIso: String, endIso: String): List<AvailabilitySlot> {
        val response: JsonObject = httpClient.get("$baseUrl/api/v1/student/availability?start=$startIso&end=$endIso").body()
        return Json.decodeFromJsonElement(ListSerializerCache.availabilityList, response["items"]!!)
    }

    override suspend fun studentBookings(): List<BookingSummary> {
        val response: JsonObject = httpClient.get("$baseUrl/api/v1/student/bookings").body()
        return Json.decodeFromJsonElement(ListSerializerCache.bookingList, response["items"]!!)
    }

    override suspend fun createStudentBooking(availabilityId: Int): Int {
        val response: JsonObject = httpClient.post("$baseUrl/api/v1/student/bookings") {
            contentType(ContentType.Application.Json)
            setBody(mapOf("availability_id" to availabilityId))
        }.body()
        return response["booking_id"]!!.jsonPrimitive.int
    }

    override suspend fun teacherBookings(): List<BookingSummary> {
        val response: JsonObject = httpClient.get("$baseUrl/api/v1/teacher/bookings").body()
        return Json.decodeFromJsonElement(ListSerializerCache.bookingList, response["items"]!!)
    }

    override suspend fun teacherSetPresent(bookingId: Int) {
        httpClient.post("$baseUrl/api/v1/teacher/bookings/$bookingId/present")
    }

    override suspend fun teacherSetAbsent(bookingId: Int) {
        httpClient.post("$baseUrl/api/v1/teacher/bookings/$bookingId/absent")
    }

    override suspend fun adminBookings(): List<BookingSummary> {
        val response: JsonObject = httpClient.get("$baseUrl/api/v1/admin/bookings").body()
        return Json.decodeFromJsonElement(ListSerializerCache.bookingList, response["items"]!!)
    }

    override suspend fun adminCancelBooking(bookingId: Int) {
        httpClient.post("$baseUrl/api/v1/admin/bookings/$bookingId/cancel")
    }
}
