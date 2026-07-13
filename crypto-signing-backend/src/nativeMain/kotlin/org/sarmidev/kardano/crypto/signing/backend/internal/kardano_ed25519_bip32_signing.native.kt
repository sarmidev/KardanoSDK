

@file:Suppress("RemoveRedundantBackticks")
@file:OptIn(ExperimentalForeignApi::class)

package org.sarmidev.kardano.crypto.signing.backend.internal

// Common helper code.
//
// Ideally this would live in a separate .kt file where it can be unittested etc
// in isolation, and perhaps even published as a re-useable package.
//
// However, it's important that the details of how this helper code works (e.g. the
// way that different builtin types are passed across the FFI) exactly match what's
// expected by the Rust code on the other side of the interface. In practice right
// now that means coming from the exact some version of `uniffi` that was used to
// compile the Rust component. The easiest way to ensure this is to bundle the Kotlin
// helpers directly inline like we're doing here.

import kotlinx.cinterop.ByteVar
import kotlinx.cinterop.COpaquePointerVar
import kotlinx.cinterop.CPointer
import kotlinx.cinterop.CValue
import kotlinx.cinterop.DoubleVar
import kotlinx.cinterop.ExperimentalForeignApi
import kotlinx.cinterop.FloatVar
import kotlinx.cinterop.IntVar
import kotlinx.cinterop.LongVar
import kotlinx.cinterop.ShortVar
import kotlinx.cinterop.get
import kotlinx.cinterop.pointed
import kotlinx.cinterop.reinterpret
import kotlinx.cinterop.set
import kotlinx.cinterop.staticCFunction
import kotlinx.cinterop.useContents
import kotlinx.cinterop.addressOf
import kotlinx.cinterop.alloc
import kotlinx.cinterop.cValue
import kotlinx.cinterop.convert
import kotlinx.cinterop.memScoped
import kotlinx.cinterop.plus
import kotlinx.cinterop.ptr
import kotlinx.cinterop.readValue
import kotlinx.cinterop.toCPointer
import kotlinx.cinterop.usePinned
import kotlin.experimental.ExperimentalNativeApi
import kotlinx.cinterop.nativeHeap
import kotlinx.cinterop.value
import kotlinx.cinterop.CFunction
import kotlinx.cinterop.write
import kotlin.coroutines.resume
import platform.posix.memcpy


internal typealias Pointer = CPointer<out kotlinx.cinterop.CPointed>
internal val NullPointer: Pointer? = null
internal fun Pointer.toLong(): Long = rawValue.toLong()
internal fun kotlin.Long.toPointer(): Pointer = requireNotNull(this.toCPointer())


public class ByteBuffer(
    internal val pointer: CPointer<kotlinx.cinterop.ByteVar>,
    internal val capacity: Int,
    internal var position: Int = 0,
) {
    public fun position(): Int = position

    public fun hasRemaining(): Boolean = capacity != position

    private fun checkRemaining(bytes: Int) {
        val remaining = capacity - position
        require(bytes <= remaining) {
            "buffer is exhausted: required: $bytes, remaining: $remaining, capacity: $capacity, position: $position"
        }
    }

    public fun get(): Byte {
        checkRemaining(1)
        return pointer[position++]
    }

    public fun get(bytesToRead: Int): ByteArray {
        checkRemaining(bytesToRead)
        val result = ByteArray(bytesToRead)
        if (result.isNotEmpty()) {
            result.usePinned { pinned ->
                memcpy(pinned.addressOf(0), pointer + position, bytesToRead.convert())
            }
            position += bytesToRead
        }
        return result
    }

    public fun getShort(): Short {
        checkRemaining(2)
        return (((pointer[position++].toInt() and 0xff) shl 8)
                or (pointer[position++].toInt() and 0xff)).toShort()
    }

    public fun getInt(): Int {
        checkRemaining(4)
        return (((pointer[position++].toInt() and 0xff) shl 24)
                or ((pointer[position++].toInt() and 0xff) shl 16)
                or ((pointer[position++].toInt() and 0xff) shl 8)
                or (pointer[position++].toInt() and 0xff))
    }

    public fun getLong(): Long {
        checkRemaining(8)
        return (((pointer[position++].toLong() and 0xffL) shl 56)
                or ((pointer[position++].toLong() and 0xffL) shl 48)
                or ((pointer[position++].toLong() and 0xffL) shl 40)
                or ((pointer[position++].toLong() and 0xffL) shl 32)
                or ((pointer[position++].toLong() and 0xffL) shl 24)
                or ((pointer[position++].toLong() and 0xffL) shl 16)
                or ((pointer[position++].toLong() and 0xffL) shl 8)
                or (pointer[position++].toLong() and 0xffL))
    }

    public fun getFloat(): Float = Float.fromBits(getInt())

    public fun getDouble(): Double = Double.fromBits(getLong())

    public fun put(value: Byte) {
        checkRemaining(1)
        pointer[position++] = value
    }

    public fun put(src: ByteArray) {
        checkRemaining(src.size)
        if (src.isNotEmpty()) {
            src.usePinned { pinned ->
                memcpy(pointer + position, pinned.addressOf(0), src.size.convert())
            }
            position += src.size
        }
    }

    public fun putShort(value: Short) {
        checkRemaining(2)
        pointer[position++] = (value.toInt() ushr 8 and 0xff).toByte()
        pointer[position++] = (value.toInt() and 0xff).toByte()
    }

    public fun putInt(value: Int) {
        checkRemaining(4)
        pointer[position++] = (value ushr 24 and 0xff).toByte()
        pointer[position++] = (value ushr 16 and 0xff).toByte()
        pointer[position++] = (value ushr 8 and 0xff).toByte()
        pointer[position++] = (value and 0xff).toByte()
    }

    public fun putLong(value: Long) {
        checkRemaining(8)
        pointer[position++] = (value ushr 56 and 0xffL).toByte()
        pointer[position++] = (value ushr 48 and 0xffL).toByte()
        pointer[position++] = (value ushr 40 and 0xffL).toByte()
        pointer[position++] = (value ushr 32 and 0xffL).toByte()
        pointer[position++] = (value ushr 24 and 0xffL).toByte()
        pointer[position++] = (value ushr 16 and 0xffL).toByte()
        pointer[position++] = (value ushr 8 and 0xffL).toByte()
        pointer[position++] = (value and 0xffL).toByte()
    }

    public fun putFloat(value: Float): Unit = putInt(value.toRawBits())

    public fun putDouble(value: Double): Unit = putLong(value.toRawBits())
}
public fun RustBuffer.setValue(array: RustBufferByValue) {
    this.data = array.data
    this.len = array.len
    this.capacity = array.capacity
}

internal object RustBufferHelper {
    internal fun allocValue(size: ULong = 0UL): RustBufferByValue = uniffiRustCall { status ->
        // Note: need to convert the size to a `Long` value to make this work with JVM.
        UniffiLib.ffi_kardano_ed25519_bip32_signing_rustbuffer_alloc(size.toLong(), status)
    }.also {
        if(it.data == null) {
            throw RuntimeException("RustBuffer.alloc() returned null data pointer (size=${size})")
        }
    }

    internal fun free(buf: RustBufferByValue) = uniffiRustCall { status ->
        UniffiLib.ffi_kardano_ed25519_bip32_signing_rustbuffer_free(buf, status)
    }
}

public typealias RustBuffer = CPointer<kardano_ed25519_bip32_signing.cinterop.RustBuffer>

public var RustBuffer.capacity: Long
    get() = pointed.capacity
    set(value) { pointed.capacity = value }
public var RustBuffer.len: Long
    get() = pointed.len
    set(value) { pointed.len = value }
public var RustBuffer.data: Pointer?
    get() = pointed.data
    set(value) { pointed.data = value?.reinterpret() }
public fun RustBuffer.asByteBuffer(): ByteBuffer? {
    require(pointed.len <= Int.MAX_VALUE) {
        val length = pointed.len
        "cannot handle RustBuffer longer than Int.MAX_VALUE bytes: length is $length"
    }
    return ByteBuffer(
        pointed.data?.reinterpret<kotlinx.cinterop.ByteVar>() ?: return null,
        pointed.len.toInt(),
    )
}

public typealias RustBufferByValue = CValue<kardano_ed25519_bip32_signing.cinterop.RustBuffer>
public fun RustBufferByValue(
    capacity: Long,
    len: Long,
    data: Pointer?,
): RustBufferByValue {
    return cValue<kardano_ed25519_bip32_signing.cinterop.RustBuffer> {
        this.capacity = capacity
        this.len = len
        this.data = data?.reinterpret()
    }
}
public val RustBufferByValue.capacity: Long
    get() = useContents { capacity }
public val RustBufferByValue.len: Long
    get() = useContents { len }
public val RustBufferByValue.data: Pointer?
    get() = useContents { data }
public fun RustBufferByValue.asByteBuffer(): ByteBuffer? {
    require(len <= Int.MAX_VALUE) {
        val length = len
        "cannot handle RustBuffer longer than Int.MAX_VALUE bytes: length is $length"
    }
    return ByteBuffer(
        data?.reinterpret<kotlinx.cinterop.ByteVar>() ?: return null,
        len.toInt(),
    )
}

internal typealias ForeignBytes = CPointer<kardano_ed25519_bip32_signing.cinterop.ForeignBytes>
internal var ForeignBytes.len: Int
    get() = pointed.len
    set(value) { pointed.len = value }
internal var ForeignBytes.data: Pointer?
    get() = pointed.data
    set(value) { pointed.data = value?.reinterpret() }

internal typealias ForeignBytesByValue = CValue<kardano_ed25519_bip32_signing.cinterop.ForeignBytes>
internal val ForeignBytesByValue.len: Int
    get() = useContents { len }
internal val ForeignBytesByValue.data: Pointer?
    get() = useContents { data }

public interface FfiConverter<KotlinType, FfiType> {
    // Convert an FFI type to a Kotlin type
    public fun lift(value: FfiType): KotlinType

    // Convert an Kotlin type to an FFI type
    public fun lower(value: KotlinType): FfiType

    // Read a Kotlin type from a `ByteBuffer`
    public fun read(buf: ByteBuffer): KotlinType

    // Calculate bytes to allocate when creating a `RustBuffer`
    //
    // This must return at least as many bytes as the write() function will
    // write. It can return more bytes than needed, for example when writing
    // Strings we can't know the exact bytes needed until we the UTF-8
    // encoding, so we pessimistically allocate the largest size possible (3
    // bytes per codepoint).  Allocating extra bytes is not really a big deal
    // because the `RustBuffer` is short-lived.
    public fun allocationSize(value: KotlinType): ULong

    // Write a Kotlin type to a `ByteBuffer`
    public fun write(value: KotlinType, buf: ByteBuffer)

    // Lower a value into a `RustBuffer`
    //
    // This method lowers a value into a `RustBuffer` rather than the normal
    // FfiType.  It's used by the callback interface code.  Callback interface
    // returns are always serialized into a `RustBuffer` regardless of their
    // normal FFI type.
    public fun lowerIntoRustBuffer(value: KotlinType): RustBufferByValue {
        val rbuf = RustBufferHelper.allocValue(allocationSize(value))
        val bbuf = rbuf.asByteBuffer()!!
        write(value, bbuf)
        return RustBufferByValue(
            capacity = rbuf.capacity,
            len = bbuf.position().toLong(),
            data = rbuf.data,
        )
    }

    // Lift a value from a `RustBuffer`.
    //
    // This here mostly because of the symmetry with `lowerIntoRustBuffer()`.
    // It's currently only used by the `FfiConverterRustBuffer` class below.
    public fun liftFromRustBuffer(rbuf: RustBufferByValue): KotlinType {
        val byteBuf = rbuf.asByteBuffer()!!
        try {
           val item = read(byteBuf)
           if (byteBuf.hasRemaining()) {
               throw RuntimeException("junk remaining in buffer after lifting, something is very wrong!!")
           }
           return item
        } finally {
            RustBufferHelper.free(rbuf)
        }
    }
}

// FfiConverter that uses `RustBuffer` as the FfiType
public interface FfiConverterRustBuffer<KotlinType>: FfiConverter<KotlinType, RustBufferByValue> {
    override fun lift(value: RustBufferByValue): KotlinType = liftFromRustBuffer(value)
    override fun lower(value: KotlinType): RustBufferByValue = lowerIntoRustBuffer(value)
}

internal const val UNIFFI_CALL_SUCCESS = 0.toByte()
internal const val UNIFFI_CALL_ERROR = 1.toByte()
internal const val UNIFFI_CALL_UNEXPECTED_ERROR = 2.toByte()

// Default Implementations
internal fun UniffiRustCallStatus.isSuccess(): Boolean
    = code == UNIFFI_CALL_SUCCESS

internal fun UniffiRustCallStatus.isError(): Boolean
    = code == UNIFFI_CALL_ERROR

internal fun UniffiRustCallStatus.isPanic(): Boolean
    = code == UNIFFI_CALL_UNEXPECTED_ERROR

internal fun UniffiRustCallStatusByValue.isSuccess(): Boolean
    = code == UNIFFI_CALL_SUCCESS

internal fun UniffiRustCallStatusByValue.isError(): Boolean
    = code == UNIFFI_CALL_ERROR

internal fun UniffiRustCallStatusByValue.isPanic(): Boolean
    = code == UNIFFI_CALL_UNEXPECTED_ERROR

// Each top-level error class has a companion object that can lift the error from the call status's rust buffer
public interface UniffiRustCallStatusErrorHandler<E> {
    public fun lift(errorBuf: RustBufferByValue): E
}

// Helpers for calling Rust
// In practice we usually need to be synchronized to call this correctly, so it doesn't
// synchronize itself

// Call a rust function that returns a Result<>.  Pass in the Error class companion that corresponds to the Err
internal inline fun <U, E: kotlin.Exception> uniffiRustCallWithError(errorHandler: UniffiRustCallStatusErrorHandler<E>, crossinline callback: (UniffiRustCallStatus) -> U): U {
    return UniffiRustCallStatusHelper.withReference() { status ->
        val returnValue = callback(status)
        uniffiCheckCallStatus(errorHandler, status)
        returnValue
    }
}

// Check `status` and throw an error if the call wasn't successful
internal fun<E: kotlin.Exception> uniffiCheckCallStatus(errorHandler: UniffiRustCallStatusErrorHandler<E>, status: UniffiRustCallStatus) {
    if (status.isSuccess()) {
        return
    } else if (status.isError()) {
        throw errorHandler.lift(status.errorBuf)
    } else if (status.isPanic()) {
        // when the rust code sees a panic, it tries to construct a rustbuffer
        // with the message.  but if that code panics, then it just sends back
        // an empty buffer.
        if (status.errorBuf.len > 0) {
            throw InternalException(FfiConverterString.lift(status.errorBuf))
        } else {
            throw InternalException("Rust panic")
        }
    } else {
        throw InternalException("Unknown rust call status: $status.code")
    }
}

// UniffiRustCallStatusErrorHandler implementation for times when we don't expect a CALL_ERROR
public object UniffiNullRustCallStatusErrorHandler: UniffiRustCallStatusErrorHandler<InternalException> {
    override fun lift(errorBuf: RustBufferByValue): InternalException {
        RustBufferHelper.free(errorBuf)
        return InternalException("Unexpected CALL_ERROR")
    }
}

// Call a rust function that returns a plain value
internal inline fun <U> uniffiRustCall(crossinline callback: (UniffiRustCallStatus) -> U): U {
    return uniffiRustCallWithError(UniffiNullRustCallStatusErrorHandler, callback)
}

internal inline fun<T> uniffiTraitInterfaceCall(
    callStatus: UniffiRustCallStatus,
    makeCall: () -> T,
    writeReturn: (T) -> Unit,
) {
    try {
        writeReturn(makeCall())
    } catch(e: kotlin.Exception) {
        callStatus.code = UNIFFI_CALL_UNEXPECTED_ERROR
        callStatus.errorBuf = FfiConverterString.lower(e.toString())
    }
}

internal inline fun<T, reified E: Throwable> uniffiTraitInterfaceCallWithError(
    callStatus: UniffiRustCallStatus,
    makeCall: () -> T,
    writeReturn: (T) -> Unit,
    lowerError: (E) -> RustBufferByValue
) {
    try {
        writeReturn(makeCall())
    } catch(e: kotlin.Exception) {
        if (e is E) {
            callStatus.code = UNIFFI_CALL_ERROR
            callStatus.errorBuf = lowerError(e)
        } else {
            callStatus.code = UNIFFI_CALL_UNEXPECTED_ERROR
            callStatus.errorBuf = FfiConverterString.lower(e.toString())
        }
    }
}

internal typealias UniffiRustCallStatus = CPointer<kardano_ed25519_bip32_signing.cinterop.UniffiRustCallStatus>
internal var UniffiRustCallStatus.code: Byte
    get() = pointed.code
    set(value) { pointed.code = value }
internal var UniffiRustCallStatus.errorBuf: RustBufferByValue
    get() = pointed.errorBuf.readValue()
    set(value) { value.place(pointed.errorBuf.ptr) }

internal typealias UniffiRustCallStatusByValue = CValue<kardano_ed25519_bip32_signing.cinterop.UniffiRustCallStatus>
internal fun UniffiRustCallStatusByValue(
    code: Byte,
    errorBuf: RustBufferByValue
): UniffiRustCallStatusByValue {
    return cValue<kardano_ed25519_bip32_signing.cinterop.UniffiRustCallStatus> {
        this.code = code
        errorBuf.write(this.errorBuf.rawPtr)
    }
}
internal val UniffiRustCallStatusByValue.code: Byte
    get() = useContents { code }
internal val UniffiRustCallStatusByValue.errorBuf: RustBufferByValue
    get() = useContents { errorBuf.readValue() }

internal object UniffiRustCallStatusHelper {
    fun allocValue() = cValue<kardano_ed25519_bip32_signing.cinterop.UniffiRustCallStatus>()
    fun <U> withReference(
        block: (UniffiRustCallStatus) -> U
    ): U {
        return memScoped {
            val status = alloc<kardano_ed25519_bip32_signing.cinterop.UniffiRustCallStatus>()
            block(status.ptr)
        }
    }
}

internal class UniffiHandleMap<T: Any> {
    private val mapLock = kotlinx.atomicfu.locks.ReentrantLock()
    private val map = HashMap<Long, T>()

    // We'll start at 1L to prevent "Null Pointers" in native's `interpretCPointer`
    private val counter: kotlinx.atomicfu.AtomicLong = kotlinx.atomicfu.atomic(1L)

    internal val size: Int
        get() = map.size

    // Insert a new object into the handle map and get a handle for it
    internal fun insert(obj: T): Long {
        val handle = counter.getAndAdd(1)
        syncAccess { map.put(handle, obj) }
        return handle
    }

    // Get an object from the handle map
    internal fun get(handle: Long): T {
        return syncAccess { map.get(handle) } ?: throw InternalException("UniffiHandleMap.get: Invalid handle")
    }

    // Remove an entry from the handlemap and get the Kotlin object back
    internal fun remove(handle: Long): T {
        return syncAccess { map.remove(handle) } ?: throw InternalException("UniffiHandleMap.remove: Invalid handle")
    }

    internal fun <T> syncAccess(block: () -> T): T {
        mapLock.lock()
        try {
            return block()
        } finally {
            mapLock.unlock()
        }
    }
}

internal typealias ByteByReference = CPointer<ByteVar>
internal fun ByteByReference.setValue(value: Byte) {
    this.pointed.value = value
}
internal fun ByteByReference.getValue() : Byte {
    return this.pointed.value
}

internal typealias DoubleByReference = CPointer<DoubleVar>
internal fun DoubleByReference.setValue(value: Double) {
    this.pointed.value = value
}
internal fun DoubleByReference.getValue() : Double {
    return this.pointed.value
}

internal typealias FloatByReference = CPointer<FloatVar>
internal fun FloatByReference.setValue(value: Float) {
    this.pointed.value = value
}
internal fun FloatByReference.getValue() : Float {
    return this.pointed.value
}

internal typealias IntByReference = CPointer<IntVar>
internal fun IntByReference.setValue(value: Int) {
    this.pointed.value = value
}
internal fun IntByReference.getValue() : Int {
    return this.pointed.value
}

internal typealias LongByReference = CPointer<LongVar>
internal fun LongByReference.setValue(value: Long) {
    this.pointed.value = value
}
internal fun LongByReference.getValue() : Long {
    return this.pointed.value
}

internal typealias PointerByReference = CPointer<COpaquePointerVar>
internal fun PointerByReference.setValue(value: Pointer?) {
    this.pointed.value = value
}
internal fun PointerByReference.getValue(): Pointer? {
    return this.pointed.value
}

internal typealias ShortByReference = CPointer<ShortVar>
internal fun ShortByReference.setValue(value: Short) {
    this.pointed.value = value
}
internal fun ShortByReference.getValue(): Short {
    return this.pointed.value
}

// Contains loading, initialization code,
// and the FFI Function declarations.

internal typealias UniffiRustFutureContinuationCallback = kardano_ed25519_bip32_signing.cinterop.UniffiRustFutureContinuationCallback
internal typealias UniffiForeignFutureFree = kardano_ed25519_bip32_signing.cinterop.UniffiForeignFutureFree
internal typealias UniffiCallbackInterfaceFree = kardano_ed25519_bip32_signing.cinterop.UniffiCallbackInterfaceFree
internal typealias UniffiForeignFuture = CPointer<kardano_ed25519_bip32_signing.cinterop.UniffiForeignFuture>

internal var UniffiForeignFuture.`handle`: Long
    get() = pointed.`handle`
    set(value) {
        pointed.`handle` = value
    }

internal var UniffiForeignFuture.`free`: UniffiForeignFutureFree?
    get() = pointed.`free`
    set(value) {
        pointed.`free` = value
    }


internal fun UniffiForeignFuture.uniffiSetValue(other: UniffiForeignFuture) {
    `handle` = other.`handle`
    `free` = other.`free`
}
internal fun UniffiForeignFuture.uniffiSetValue(other: UniffiForeignFutureUniffiByValue) {
    `handle` = other.`handle`
    `free` = other.`free`
}

internal typealias UniffiForeignFutureUniffiByValue = CValue<kardano_ed25519_bip32_signing.cinterop.UniffiForeignFuture>
internal fun UniffiForeignFutureUniffiByValue(
    `handle`: Long,
    `free`: UniffiForeignFutureFree?,
): UniffiForeignFutureUniffiByValue {
    return cValue<kardano_ed25519_bip32_signing.cinterop.UniffiForeignFuture> {
        this.`handle` = `handle`
        this.`free` = `free`
    }
}


internal val UniffiForeignFutureUniffiByValue.`handle`: Long
    get() = useContents { `handle` }

internal val UniffiForeignFutureUniffiByValue.`free`: UniffiForeignFutureFree?
    get() = useContents { `free` }

internal typealias UniffiForeignFutureStructU8 = CPointer<kardano_ed25519_bip32_signing.cinterop.UniffiForeignFutureStructU8>

internal var UniffiForeignFutureStructU8.`returnValue`: Byte
    get() = pointed.`returnValue`
    set(value) {
        pointed.`returnValue` = value
    }

internal var UniffiForeignFutureStructU8.`callStatus`: UniffiRustCallStatusByValue
    get() = pointed.`callStatus`.readValue()
    set(value) {
        value.write(pointed.`callStatus`.rawPtr)
    }


internal fun UniffiForeignFutureStructU8.uniffiSetValue(other: UniffiForeignFutureStructU8) {
    `returnValue` = other.`returnValue`
    `callStatus` = other.`callStatus`
}
internal fun UniffiForeignFutureStructU8.uniffiSetValue(other: UniffiForeignFutureStructU8UniffiByValue) {
    `returnValue` = other.`returnValue`
    `callStatus` = other.`callStatus`
}

internal typealias UniffiForeignFutureStructU8UniffiByValue = CValue<kardano_ed25519_bip32_signing.cinterop.UniffiForeignFutureStructU8>
internal fun UniffiForeignFutureStructU8UniffiByValue(
    `returnValue`: Byte,
    `callStatus`: UniffiRustCallStatusByValue,
): UniffiForeignFutureStructU8UniffiByValue {
    return cValue<kardano_ed25519_bip32_signing.cinterop.UniffiForeignFutureStructU8> {
        this.`returnValue` = `returnValue`
        `callStatus`.write(this.`callStatus`.rawPtr)
    }
}


internal val UniffiForeignFutureStructU8UniffiByValue.`returnValue`: Byte
    get() = useContents { `returnValue` }

internal val UniffiForeignFutureStructU8UniffiByValue.`callStatus`: UniffiRustCallStatusByValue
    get() = useContents { `callStatus`.readValue() }

internal typealias UniffiForeignFutureCompleteU8 = kardano_ed25519_bip32_signing.cinterop.UniffiForeignFutureCompleteU8
internal typealias UniffiForeignFutureStructI8 = CPointer<kardano_ed25519_bip32_signing.cinterop.UniffiForeignFutureStructI8>

internal var UniffiForeignFutureStructI8.`returnValue`: Byte
    get() = pointed.`returnValue`
    set(value) {
        pointed.`returnValue` = value
    }

internal var UniffiForeignFutureStructI8.`callStatus`: UniffiRustCallStatusByValue
    get() = pointed.`callStatus`.readValue()
    set(value) {
        value.write(pointed.`callStatus`.rawPtr)
    }


internal fun UniffiForeignFutureStructI8.uniffiSetValue(other: UniffiForeignFutureStructI8) {
    `returnValue` = other.`returnValue`
    `callStatus` = other.`callStatus`
}
internal fun UniffiForeignFutureStructI8.uniffiSetValue(other: UniffiForeignFutureStructI8UniffiByValue) {
    `returnValue` = other.`returnValue`
    `callStatus` = other.`callStatus`
}

internal typealias UniffiForeignFutureStructI8UniffiByValue = CValue<kardano_ed25519_bip32_signing.cinterop.UniffiForeignFutureStructI8>
internal fun UniffiForeignFutureStructI8UniffiByValue(
    `returnValue`: Byte,
    `callStatus`: UniffiRustCallStatusByValue,
): UniffiForeignFutureStructI8UniffiByValue {
    return cValue<kardano_ed25519_bip32_signing.cinterop.UniffiForeignFutureStructI8> {
        this.`returnValue` = `returnValue`
        `callStatus`.write(this.`callStatus`.rawPtr)
    }
}


internal val UniffiForeignFutureStructI8UniffiByValue.`returnValue`: Byte
    get() = useContents { `returnValue` }

internal val UniffiForeignFutureStructI8UniffiByValue.`callStatus`: UniffiRustCallStatusByValue
    get() = useContents { `callStatus`.readValue() }

internal typealias UniffiForeignFutureCompleteI8 = kardano_ed25519_bip32_signing.cinterop.UniffiForeignFutureCompleteI8
internal typealias UniffiForeignFutureStructU16 = CPointer<kardano_ed25519_bip32_signing.cinterop.UniffiForeignFutureStructU16>

internal var UniffiForeignFutureStructU16.`returnValue`: Short
    get() = pointed.`returnValue`
    set(value) {
        pointed.`returnValue` = value
    }

internal var UniffiForeignFutureStructU16.`callStatus`: UniffiRustCallStatusByValue
    get() = pointed.`callStatus`.readValue()
    set(value) {
        value.write(pointed.`callStatus`.rawPtr)
    }


internal fun UniffiForeignFutureStructU16.uniffiSetValue(other: UniffiForeignFutureStructU16) {
    `returnValue` = other.`returnValue`
    `callStatus` = other.`callStatus`
}
internal fun UniffiForeignFutureStructU16.uniffiSetValue(other: UniffiForeignFutureStructU16UniffiByValue) {
    `returnValue` = other.`returnValue`
    `callStatus` = other.`callStatus`
}

internal typealias UniffiForeignFutureStructU16UniffiByValue = CValue<kardano_ed25519_bip32_signing.cinterop.UniffiForeignFutureStructU16>
internal fun UniffiForeignFutureStructU16UniffiByValue(
    `returnValue`: Short,
    `callStatus`: UniffiRustCallStatusByValue,
): UniffiForeignFutureStructU16UniffiByValue {
    return cValue<kardano_ed25519_bip32_signing.cinterop.UniffiForeignFutureStructU16> {
        this.`returnValue` = `returnValue`
        `callStatus`.write(this.`callStatus`.rawPtr)
    }
}


internal val UniffiForeignFutureStructU16UniffiByValue.`returnValue`: Short
    get() = useContents { `returnValue` }

internal val UniffiForeignFutureStructU16UniffiByValue.`callStatus`: UniffiRustCallStatusByValue
    get() = useContents { `callStatus`.readValue() }

internal typealias UniffiForeignFutureCompleteU16 = kardano_ed25519_bip32_signing.cinterop.UniffiForeignFutureCompleteU16
internal typealias UniffiForeignFutureStructI16 = CPointer<kardano_ed25519_bip32_signing.cinterop.UniffiForeignFutureStructI16>

internal var UniffiForeignFutureStructI16.`returnValue`: Short
    get() = pointed.`returnValue`
    set(value) {
        pointed.`returnValue` = value
    }

internal var UniffiForeignFutureStructI16.`callStatus`: UniffiRustCallStatusByValue
    get() = pointed.`callStatus`.readValue()
    set(value) {
        value.write(pointed.`callStatus`.rawPtr)
    }


internal fun UniffiForeignFutureStructI16.uniffiSetValue(other: UniffiForeignFutureStructI16) {
    `returnValue` = other.`returnValue`
    `callStatus` = other.`callStatus`
}
internal fun UniffiForeignFutureStructI16.uniffiSetValue(other: UniffiForeignFutureStructI16UniffiByValue) {
    `returnValue` = other.`returnValue`
    `callStatus` = other.`callStatus`
}

internal typealias UniffiForeignFutureStructI16UniffiByValue = CValue<kardano_ed25519_bip32_signing.cinterop.UniffiForeignFutureStructI16>
internal fun UniffiForeignFutureStructI16UniffiByValue(
    `returnValue`: Short,
    `callStatus`: UniffiRustCallStatusByValue,
): UniffiForeignFutureStructI16UniffiByValue {
    return cValue<kardano_ed25519_bip32_signing.cinterop.UniffiForeignFutureStructI16> {
        this.`returnValue` = `returnValue`
        `callStatus`.write(this.`callStatus`.rawPtr)
    }
}


internal val UniffiForeignFutureStructI16UniffiByValue.`returnValue`: Short
    get() = useContents { `returnValue` }

internal val UniffiForeignFutureStructI16UniffiByValue.`callStatus`: UniffiRustCallStatusByValue
    get() = useContents { `callStatus`.readValue() }

internal typealias UniffiForeignFutureCompleteI16 = kardano_ed25519_bip32_signing.cinterop.UniffiForeignFutureCompleteI16
internal typealias UniffiForeignFutureStructU32 = CPointer<kardano_ed25519_bip32_signing.cinterop.UniffiForeignFutureStructU32>

internal var UniffiForeignFutureStructU32.`returnValue`: Int
    get() = pointed.`returnValue`
    set(value) {
        pointed.`returnValue` = value
    }

internal var UniffiForeignFutureStructU32.`callStatus`: UniffiRustCallStatusByValue
    get() = pointed.`callStatus`.readValue()
    set(value) {
        value.write(pointed.`callStatus`.rawPtr)
    }


internal fun UniffiForeignFutureStructU32.uniffiSetValue(other: UniffiForeignFutureStructU32) {
    `returnValue` = other.`returnValue`
    `callStatus` = other.`callStatus`
}
internal fun UniffiForeignFutureStructU32.uniffiSetValue(other: UniffiForeignFutureStructU32UniffiByValue) {
    `returnValue` = other.`returnValue`
    `callStatus` = other.`callStatus`
}

internal typealias UniffiForeignFutureStructU32UniffiByValue = CValue<kardano_ed25519_bip32_signing.cinterop.UniffiForeignFutureStructU32>
internal fun UniffiForeignFutureStructU32UniffiByValue(
    `returnValue`: Int,
    `callStatus`: UniffiRustCallStatusByValue,
): UniffiForeignFutureStructU32UniffiByValue {
    return cValue<kardano_ed25519_bip32_signing.cinterop.UniffiForeignFutureStructU32> {
        this.`returnValue` = `returnValue`
        `callStatus`.write(this.`callStatus`.rawPtr)
    }
}


internal val UniffiForeignFutureStructU32UniffiByValue.`returnValue`: Int
    get() = useContents { `returnValue` }

internal val UniffiForeignFutureStructU32UniffiByValue.`callStatus`: UniffiRustCallStatusByValue
    get() = useContents { `callStatus`.readValue() }

internal typealias UniffiForeignFutureCompleteU32 = kardano_ed25519_bip32_signing.cinterop.UniffiForeignFutureCompleteU32
internal typealias UniffiForeignFutureStructI32 = CPointer<kardano_ed25519_bip32_signing.cinterop.UniffiForeignFutureStructI32>

internal var UniffiForeignFutureStructI32.`returnValue`: Int
    get() = pointed.`returnValue`
    set(value) {
        pointed.`returnValue` = value
    }

internal var UniffiForeignFutureStructI32.`callStatus`: UniffiRustCallStatusByValue
    get() = pointed.`callStatus`.readValue()
    set(value) {
        value.write(pointed.`callStatus`.rawPtr)
    }


internal fun UniffiForeignFutureStructI32.uniffiSetValue(other: UniffiForeignFutureStructI32) {
    `returnValue` = other.`returnValue`
    `callStatus` = other.`callStatus`
}
internal fun UniffiForeignFutureStructI32.uniffiSetValue(other: UniffiForeignFutureStructI32UniffiByValue) {
    `returnValue` = other.`returnValue`
    `callStatus` = other.`callStatus`
}

internal typealias UniffiForeignFutureStructI32UniffiByValue = CValue<kardano_ed25519_bip32_signing.cinterop.UniffiForeignFutureStructI32>
internal fun UniffiForeignFutureStructI32UniffiByValue(
    `returnValue`: Int,
    `callStatus`: UniffiRustCallStatusByValue,
): UniffiForeignFutureStructI32UniffiByValue {
    return cValue<kardano_ed25519_bip32_signing.cinterop.UniffiForeignFutureStructI32> {
        this.`returnValue` = `returnValue`
        `callStatus`.write(this.`callStatus`.rawPtr)
    }
}


internal val UniffiForeignFutureStructI32UniffiByValue.`returnValue`: Int
    get() = useContents { `returnValue` }

internal val UniffiForeignFutureStructI32UniffiByValue.`callStatus`: UniffiRustCallStatusByValue
    get() = useContents { `callStatus`.readValue() }

internal typealias UniffiForeignFutureCompleteI32 = kardano_ed25519_bip32_signing.cinterop.UniffiForeignFutureCompleteI32
internal typealias UniffiForeignFutureStructU64 = CPointer<kardano_ed25519_bip32_signing.cinterop.UniffiForeignFutureStructU64>

internal var UniffiForeignFutureStructU64.`returnValue`: Long
    get() = pointed.`returnValue`
    set(value) {
        pointed.`returnValue` = value
    }

internal var UniffiForeignFutureStructU64.`callStatus`: UniffiRustCallStatusByValue
    get() = pointed.`callStatus`.readValue()
    set(value) {
        value.write(pointed.`callStatus`.rawPtr)
    }


internal fun UniffiForeignFutureStructU64.uniffiSetValue(other: UniffiForeignFutureStructU64) {
    `returnValue` = other.`returnValue`
    `callStatus` = other.`callStatus`
}
internal fun UniffiForeignFutureStructU64.uniffiSetValue(other: UniffiForeignFutureStructU64UniffiByValue) {
    `returnValue` = other.`returnValue`
    `callStatus` = other.`callStatus`
}

internal typealias UniffiForeignFutureStructU64UniffiByValue = CValue<kardano_ed25519_bip32_signing.cinterop.UniffiForeignFutureStructU64>
internal fun UniffiForeignFutureStructU64UniffiByValue(
    `returnValue`: Long,
    `callStatus`: UniffiRustCallStatusByValue,
): UniffiForeignFutureStructU64UniffiByValue {
    return cValue<kardano_ed25519_bip32_signing.cinterop.UniffiForeignFutureStructU64> {
        this.`returnValue` = `returnValue`
        `callStatus`.write(this.`callStatus`.rawPtr)
    }
}


internal val UniffiForeignFutureStructU64UniffiByValue.`returnValue`: Long
    get() = useContents { `returnValue` }

internal val UniffiForeignFutureStructU64UniffiByValue.`callStatus`: UniffiRustCallStatusByValue
    get() = useContents { `callStatus`.readValue() }

internal typealias UniffiForeignFutureCompleteU64 = kardano_ed25519_bip32_signing.cinterop.UniffiForeignFutureCompleteU64
internal typealias UniffiForeignFutureStructI64 = CPointer<kardano_ed25519_bip32_signing.cinterop.UniffiForeignFutureStructI64>

internal var UniffiForeignFutureStructI64.`returnValue`: Long
    get() = pointed.`returnValue`
    set(value) {
        pointed.`returnValue` = value
    }

internal var UniffiForeignFutureStructI64.`callStatus`: UniffiRustCallStatusByValue
    get() = pointed.`callStatus`.readValue()
    set(value) {
        value.write(pointed.`callStatus`.rawPtr)
    }


internal fun UniffiForeignFutureStructI64.uniffiSetValue(other: UniffiForeignFutureStructI64) {
    `returnValue` = other.`returnValue`
    `callStatus` = other.`callStatus`
}
internal fun UniffiForeignFutureStructI64.uniffiSetValue(other: UniffiForeignFutureStructI64UniffiByValue) {
    `returnValue` = other.`returnValue`
    `callStatus` = other.`callStatus`
}

internal typealias UniffiForeignFutureStructI64UniffiByValue = CValue<kardano_ed25519_bip32_signing.cinterop.UniffiForeignFutureStructI64>
internal fun UniffiForeignFutureStructI64UniffiByValue(
    `returnValue`: Long,
    `callStatus`: UniffiRustCallStatusByValue,
): UniffiForeignFutureStructI64UniffiByValue {
    return cValue<kardano_ed25519_bip32_signing.cinterop.UniffiForeignFutureStructI64> {
        this.`returnValue` = `returnValue`
        `callStatus`.write(this.`callStatus`.rawPtr)
    }
}


internal val UniffiForeignFutureStructI64UniffiByValue.`returnValue`: Long
    get() = useContents { `returnValue` }

internal val UniffiForeignFutureStructI64UniffiByValue.`callStatus`: UniffiRustCallStatusByValue
    get() = useContents { `callStatus`.readValue() }

internal typealias UniffiForeignFutureCompleteI64 = kardano_ed25519_bip32_signing.cinterop.UniffiForeignFutureCompleteI64
internal typealias UniffiForeignFutureStructF32 = CPointer<kardano_ed25519_bip32_signing.cinterop.UniffiForeignFutureStructF32>

internal var UniffiForeignFutureStructF32.`returnValue`: Float
    get() = pointed.`returnValue`
    set(value) {
        pointed.`returnValue` = value
    }

internal var UniffiForeignFutureStructF32.`callStatus`: UniffiRustCallStatusByValue
    get() = pointed.`callStatus`.readValue()
    set(value) {
        value.write(pointed.`callStatus`.rawPtr)
    }


internal fun UniffiForeignFutureStructF32.uniffiSetValue(other: UniffiForeignFutureStructF32) {
    `returnValue` = other.`returnValue`
    `callStatus` = other.`callStatus`
}
internal fun UniffiForeignFutureStructF32.uniffiSetValue(other: UniffiForeignFutureStructF32UniffiByValue) {
    `returnValue` = other.`returnValue`
    `callStatus` = other.`callStatus`
}

internal typealias UniffiForeignFutureStructF32UniffiByValue = CValue<kardano_ed25519_bip32_signing.cinterop.UniffiForeignFutureStructF32>
internal fun UniffiForeignFutureStructF32UniffiByValue(
    `returnValue`: Float,
    `callStatus`: UniffiRustCallStatusByValue,
): UniffiForeignFutureStructF32UniffiByValue {
    return cValue<kardano_ed25519_bip32_signing.cinterop.UniffiForeignFutureStructF32> {
        this.`returnValue` = `returnValue`
        `callStatus`.write(this.`callStatus`.rawPtr)
    }
}


internal val UniffiForeignFutureStructF32UniffiByValue.`returnValue`: Float
    get() = useContents { `returnValue` }

internal val UniffiForeignFutureStructF32UniffiByValue.`callStatus`: UniffiRustCallStatusByValue
    get() = useContents { `callStatus`.readValue() }

internal typealias UniffiForeignFutureCompleteF32 = kardano_ed25519_bip32_signing.cinterop.UniffiForeignFutureCompleteF32
internal typealias UniffiForeignFutureStructF64 = CPointer<kardano_ed25519_bip32_signing.cinterop.UniffiForeignFutureStructF64>

internal var UniffiForeignFutureStructF64.`returnValue`: Double
    get() = pointed.`returnValue`
    set(value) {
        pointed.`returnValue` = value
    }

internal var UniffiForeignFutureStructF64.`callStatus`: UniffiRustCallStatusByValue
    get() = pointed.`callStatus`.readValue()
    set(value) {
        value.write(pointed.`callStatus`.rawPtr)
    }


internal fun UniffiForeignFutureStructF64.uniffiSetValue(other: UniffiForeignFutureStructF64) {
    `returnValue` = other.`returnValue`
    `callStatus` = other.`callStatus`
}
internal fun UniffiForeignFutureStructF64.uniffiSetValue(other: UniffiForeignFutureStructF64UniffiByValue) {
    `returnValue` = other.`returnValue`
    `callStatus` = other.`callStatus`
}

internal typealias UniffiForeignFutureStructF64UniffiByValue = CValue<kardano_ed25519_bip32_signing.cinterop.UniffiForeignFutureStructF64>
internal fun UniffiForeignFutureStructF64UniffiByValue(
    `returnValue`: Double,
    `callStatus`: UniffiRustCallStatusByValue,
): UniffiForeignFutureStructF64UniffiByValue {
    return cValue<kardano_ed25519_bip32_signing.cinterop.UniffiForeignFutureStructF64> {
        this.`returnValue` = `returnValue`
        `callStatus`.write(this.`callStatus`.rawPtr)
    }
}


internal val UniffiForeignFutureStructF64UniffiByValue.`returnValue`: Double
    get() = useContents { `returnValue` }

internal val UniffiForeignFutureStructF64UniffiByValue.`callStatus`: UniffiRustCallStatusByValue
    get() = useContents { `callStatus`.readValue() }

internal typealias UniffiForeignFutureCompleteF64 = kardano_ed25519_bip32_signing.cinterop.UniffiForeignFutureCompleteF64
internal typealias UniffiForeignFutureStructPointer = CPointer<kardano_ed25519_bip32_signing.cinterop.UniffiForeignFutureStructPointer>

internal var UniffiForeignFutureStructPointer.`returnValue`: Pointer?
    get() = pointed.`returnValue`
    set(value) {
        pointed.`returnValue` = value
    }

internal var UniffiForeignFutureStructPointer.`callStatus`: UniffiRustCallStatusByValue
    get() = pointed.`callStatus`.readValue()
    set(value) {
        value.write(pointed.`callStatus`.rawPtr)
    }


internal fun UniffiForeignFutureStructPointer.uniffiSetValue(other: UniffiForeignFutureStructPointer) {
    `returnValue` = other.`returnValue`
    `callStatus` = other.`callStatus`
}
internal fun UniffiForeignFutureStructPointer.uniffiSetValue(other: UniffiForeignFutureStructPointerUniffiByValue) {
    `returnValue` = other.`returnValue`
    `callStatus` = other.`callStatus`
}

internal typealias UniffiForeignFutureStructPointerUniffiByValue = CValue<kardano_ed25519_bip32_signing.cinterop.UniffiForeignFutureStructPointer>
internal fun UniffiForeignFutureStructPointerUniffiByValue(
    `returnValue`: Pointer?,
    `callStatus`: UniffiRustCallStatusByValue,
): UniffiForeignFutureStructPointerUniffiByValue {
    return cValue<kardano_ed25519_bip32_signing.cinterop.UniffiForeignFutureStructPointer> {
        this.`returnValue` = `returnValue`
        `callStatus`.write(this.`callStatus`.rawPtr)
    }
}


internal val UniffiForeignFutureStructPointerUniffiByValue.`returnValue`: Pointer?
    get() = useContents { `returnValue` }

internal val UniffiForeignFutureStructPointerUniffiByValue.`callStatus`: UniffiRustCallStatusByValue
    get() = useContents { `callStatus`.readValue() }

internal typealias UniffiForeignFutureCompletePointer = kardano_ed25519_bip32_signing.cinterop.UniffiForeignFutureCompletePointer
internal typealias UniffiForeignFutureStructRustBuffer = CPointer<kardano_ed25519_bip32_signing.cinterop.UniffiForeignFutureStructRustBuffer>

internal var UniffiForeignFutureStructRustBuffer.`returnValue`: RustBufferByValue
    get() = pointed.`returnValue`.readValue()
    set(value) {
        value.write(pointed.`returnValue`.rawPtr)
    }

internal var UniffiForeignFutureStructRustBuffer.`callStatus`: UniffiRustCallStatusByValue
    get() = pointed.`callStatus`.readValue()
    set(value) {
        value.write(pointed.`callStatus`.rawPtr)
    }


internal fun UniffiForeignFutureStructRustBuffer.uniffiSetValue(other: UniffiForeignFutureStructRustBuffer) {
    `returnValue` = other.`returnValue`
    `callStatus` = other.`callStatus`
}
internal fun UniffiForeignFutureStructRustBuffer.uniffiSetValue(other: UniffiForeignFutureStructRustBufferUniffiByValue) {
    `returnValue` = other.`returnValue`
    `callStatus` = other.`callStatus`
}

internal typealias UniffiForeignFutureStructRustBufferUniffiByValue = CValue<kardano_ed25519_bip32_signing.cinterop.UniffiForeignFutureStructRustBuffer>
internal fun UniffiForeignFutureStructRustBufferUniffiByValue(
    `returnValue`: RustBufferByValue,
    `callStatus`: UniffiRustCallStatusByValue,
): UniffiForeignFutureStructRustBufferUniffiByValue {
    return cValue<kardano_ed25519_bip32_signing.cinterop.UniffiForeignFutureStructRustBuffer> {
        `returnValue`.write(this.`returnValue`.rawPtr)
        `callStatus`.write(this.`callStatus`.rawPtr)
    }
}


internal val UniffiForeignFutureStructRustBufferUniffiByValue.`returnValue`: RustBufferByValue
    get() = useContents { `returnValue`.readValue() }

internal val UniffiForeignFutureStructRustBufferUniffiByValue.`callStatus`: UniffiRustCallStatusByValue
    get() = useContents { `callStatus`.readValue() }

internal typealias UniffiForeignFutureCompleteRustBuffer = kardano_ed25519_bip32_signing.cinterop.UniffiForeignFutureCompleteRustBuffer
internal typealias UniffiForeignFutureStructVoid = CPointer<kardano_ed25519_bip32_signing.cinterop.UniffiForeignFutureStructVoid>

internal var UniffiForeignFutureStructVoid.`callStatus`: UniffiRustCallStatusByValue
    get() = pointed.`callStatus`.readValue()
    set(value) {
        value.write(pointed.`callStatus`.rawPtr)
    }


internal fun UniffiForeignFutureStructVoid.uniffiSetValue(other: UniffiForeignFutureStructVoid) {
    `callStatus` = other.`callStatus`
}
internal fun UniffiForeignFutureStructVoid.uniffiSetValue(other: UniffiForeignFutureStructVoidUniffiByValue) {
    `callStatus` = other.`callStatus`
}

internal typealias UniffiForeignFutureStructVoidUniffiByValue = CValue<kardano_ed25519_bip32_signing.cinterop.UniffiForeignFutureStructVoid>
internal fun UniffiForeignFutureStructVoidUniffiByValue(
    `callStatus`: UniffiRustCallStatusByValue,
): UniffiForeignFutureStructVoidUniffiByValue {
    return cValue<kardano_ed25519_bip32_signing.cinterop.UniffiForeignFutureStructVoid> {
        `callStatus`.write(this.`callStatus`.rawPtr)
    }
}


internal val UniffiForeignFutureStructVoidUniffiByValue.`callStatus`: UniffiRustCallStatusByValue
    get() = useContents { `callStatus`.readValue() }

internal typealias UniffiForeignFutureCompleteVoid = kardano_ed25519_bip32_signing.cinterop.UniffiForeignFutureCompleteVoid
































































internal object UniffiLib {
    init {
    }

    fun uniffi_kardano_ed25519_bip32_signing_fn_func_derive_xpub(
        `xprv`: RustBufferByValue,
        uniffiCallStatus: UniffiRustCallStatus,
    ): RustBufferByValue = kardano_ed25519_bip32_signing.cinterop.uniffi_kardano_ed25519_bip32_signing_fn_func_derive_xpub(
        `xprv`,
        uniffiCallStatus,
    )
    fun uniffi_kardano_ed25519_bip32_signing_fn_func_sign(
        `xprv`: RustBufferByValue,
        `message`: RustBufferByValue,
        uniffiCallStatus: UniffiRustCallStatus,
    ): RustBufferByValue = kardano_ed25519_bip32_signing.cinterop.uniffi_kardano_ed25519_bip32_signing_fn_func_sign(
        `xprv`,
        `message`,
        uniffiCallStatus,
    )
    fun uniffi_kardano_ed25519_bip32_signing_fn_func_verify(
        `xpub`: RustBufferByValue,
        `message`: RustBufferByValue,
        `signature`: RustBufferByValue,
        uniffiCallStatus: UniffiRustCallStatus,
    ): Byte = kardano_ed25519_bip32_signing.cinterop.uniffi_kardano_ed25519_bip32_signing_fn_func_verify(
        `xpub`,
        `message`,
        `signature`,
        uniffiCallStatus,
    )
    fun ffi_kardano_ed25519_bip32_signing_rustbuffer_alloc(
        `size`: Long,
        uniffiCallStatus: UniffiRustCallStatus,
    ): RustBufferByValue = kardano_ed25519_bip32_signing.cinterop.ffi_kardano_ed25519_bip32_signing_rustbuffer_alloc(
        `size`,
        uniffiCallStatus,
    )
    fun ffi_kardano_ed25519_bip32_signing_rustbuffer_from_bytes(
        `bytes`: ForeignBytesByValue,
        uniffiCallStatus: UniffiRustCallStatus,
    ): RustBufferByValue = kardano_ed25519_bip32_signing.cinterop.ffi_kardano_ed25519_bip32_signing_rustbuffer_from_bytes(
        `bytes`,
        uniffiCallStatus,
    )
    fun ffi_kardano_ed25519_bip32_signing_rustbuffer_free(
        `buf`: RustBufferByValue,
        uniffiCallStatus: UniffiRustCallStatus,
    ): Unit = kardano_ed25519_bip32_signing.cinterop.ffi_kardano_ed25519_bip32_signing_rustbuffer_free(
        `buf`,
        uniffiCallStatus,
    )
    fun ffi_kardano_ed25519_bip32_signing_rustbuffer_reserve(
        `buf`: RustBufferByValue,
        `additional`: Long,
        uniffiCallStatus: UniffiRustCallStatus,
    ): RustBufferByValue = kardano_ed25519_bip32_signing.cinterop.ffi_kardano_ed25519_bip32_signing_rustbuffer_reserve(
        `buf`,
        `additional`,
        uniffiCallStatus,
    )
    fun ffi_kardano_ed25519_bip32_signing_rust_future_poll_u8(
        `handle`: Long,
        `callback`: UniffiRustFutureContinuationCallback,
        `callbackData`: Long,
    ): Unit = kardano_ed25519_bip32_signing.cinterop.ffi_kardano_ed25519_bip32_signing_rust_future_poll_u8(
        `handle`,
        `callback`,
        `callbackData`,
    )
    fun ffi_kardano_ed25519_bip32_signing_rust_future_cancel_u8(
        `handle`: Long,
    ): Unit = kardano_ed25519_bip32_signing.cinterop.ffi_kardano_ed25519_bip32_signing_rust_future_cancel_u8(
        `handle`,
    )
    fun ffi_kardano_ed25519_bip32_signing_rust_future_free_u8(
        `handle`: Long,
    ): Unit = kardano_ed25519_bip32_signing.cinterop.ffi_kardano_ed25519_bip32_signing_rust_future_free_u8(
        `handle`,
    )
    fun ffi_kardano_ed25519_bip32_signing_rust_future_complete_u8(
        `handle`: Long,
        uniffiCallStatus: UniffiRustCallStatus,
    ): Byte = kardano_ed25519_bip32_signing.cinterop.ffi_kardano_ed25519_bip32_signing_rust_future_complete_u8(
        `handle`,
        uniffiCallStatus,
    )
    fun ffi_kardano_ed25519_bip32_signing_rust_future_poll_i8(
        `handle`: Long,
        `callback`: UniffiRustFutureContinuationCallback,
        `callbackData`: Long,
    ): Unit = kardano_ed25519_bip32_signing.cinterop.ffi_kardano_ed25519_bip32_signing_rust_future_poll_i8(
        `handle`,
        `callback`,
        `callbackData`,
    )
    fun ffi_kardano_ed25519_bip32_signing_rust_future_cancel_i8(
        `handle`: Long,
    ): Unit = kardano_ed25519_bip32_signing.cinterop.ffi_kardano_ed25519_bip32_signing_rust_future_cancel_i8(
        `handle`,
    )
    fun ffi_kardano_ed25519_bip32_signing_rust_future_free_i8(
        `handle`: Long,
    ): Unit = kardano_ed25519_bip32_signing.cinterop.ffi_kardano_ed25519_bip32_signing_rust_future_free_i8(
        `handle`,
    )
    fun ffi_kardano_ed25519_bip32_signing_rust_future_complete_i8(
        `handle`: Long,
        uniffiCallStatus: UniffiRustCallStatus,
    ): Byte = kardano_ed25519_bip32_signing.cinterop.ffi_kardano_ed25519_bip32_signing_rust_future_complete_i8(
        `handle`,
        uniffiCallStatus,
    )
    fun ffi_kardano_ed25519_bip32_signing_rust_future_poll_u16(
        `handle`: Long,
        `callback`: UniffiRustFutureContinuationCallback,
        `callbackData`: Long,
    ): Unit = kardano_ed25519_bip32_signing.cinterop.ffi_kardano_ed25519_bip32_signing_rust_future_poll_u16(
        `handle`,
        `callback`,
        `callbackData`,
    )
    fun ffi_kardano_ed25519_bip32_signing_rust_future_cancel_u16(
        `handle`: Long,
    ): Unit = kardano_ed25519_bip32_signing.cinterop.ffi_kardano_ed25519_bip32_signing_rust_future_cancel_u16(
        `handle`,
    )
    fun ffi_kardano_ed25519_bip32_signing_rust_future_free_u16(
        `handle`: Long,
    ): Unit = kardano_ed25519_bip32_signing.cinterop.ffi_kardano_ed25519_bip32_signing_rust_future_free_u16(
        `handle`,
    )
    fun ffi_kardano_ed25519_bip32_signing_rust_future_complete_u16(
        `handle`: Long,
        uniffiCallStatus: UniffiRustCallStatus,
    ): Short = kardano_ed25519_bip32_signing.cinterop.ffi_kardano_ed25519_bip32_signing_rust_future_complete_u16(
        `handle`,
        uniffiCallStatus,
    )
    fun ffi_kardano_ed25519_bip32_signing_rust_future_poll_i16(
        `handle`: Long,
        `callback`: UniffiRustFutureContinuationCallback,
        `callbackData`: Long,
    ): Unit = kardano_ed25519_bip32_signing.cinterop.ffi_kardano_ed25519_bip32_signing_rust_future_poll_i16(
        `handle`,
        `callback`,
        `callbackData`,
    )
    fun ffi_kardano_ed25519_bip32_signing_rust_future_cancel_i16(
        `handle`: Long,
    ): Unit = kardano_ed25519_bip32_signing.cinterop.ffi_kardano_ed25519_bip32_signing_rust_future_cancel_i16(
        `handle`,
    )
    fun ffi_kardano_ed25519_bip32_signing_rust_future_free_i16(
        `handle`: Long,
    ): Unit = kardano_ed25519_bip32_signing.cinterop.ffi_kardano_ed25519_bip32_signing_rust_future_free_i16(
        `handle`,
    )
    fun ffi_kardano_ed25519_bip32_signing_rust_future_complete_i16(
        `handle`: Long,
        uniffiCallStatus: UniffiRustCallStatus,
    ): Short = kardano_ed25519_bip32_signing.cinterop.ffi_kardano_ed25519_bip32_signing_rust_future_complete_i16(
        `handle`,
        uniffiCallStatus,
    )
    fun ffi_kardano_ed25519_bip32_signing_rust_future_poll_u32(
        `handle`: Long,
        `callback`: UniffiRustFutureContinuationCallback,
        `callbackData`: Long,
    ): Unit = kardano_ed25519_bip32_signing.cinterop.ffi_kardano_ed25519_bip32_signing_rust_future_poll_u32(
        `handle`,
        `callback`,
        `callbackData`,
    )
    fun ffi_kardano_ed25519_bip32_signing_rust_future_cancel_u32(
        `handle`: Long,
    ): Unit = kardano_ed25519_bip32_signing.cinterop.ffi_kardano_ed25519_bip32_signing_rust_future_cancel_u32(
        `handle`,
    )
    fun ffi_kardano_ed25519_bip32_signing_rust_future_free_u32(
        `handle`: Long,
    ): Unit = kardano_ed25519_bip32_signing.cinterop.ffi_kardano_ed25519_bip32_signing_rust_future_free_u32(
        `handle`,
    )
    fun ffi_kardano_ed25519_bip32_signing_rust_future_complete_u32(
        `handle`: Long,
        uniffiCallStatus: UniffiRustCallStatus,
    ): Int = kardano_ed25519_bip32_signing.cinterop.ffi_kardano_ed25519_bip32_signing_rust_future_complete_u32(
        `handle`,
        uniffiCallStatus,
    )
    fun ffi_kardano_ed25519_bip32_signing_rust_future_poll_i32(
        `handle`: Long,
        `callback`: UniffiRustFutureContinuationCallback,
        `callbackData`: Long,
    ): Unit = kardano_ed25519_bip32_signing.cinterop.ffi_kardano_ed25519_bip32_signing_rust_future_poll_i32(
        `handle`,
        `callback`,
        `callbackData`,
    )
    fun ffi_kardano_ed25519_bip32_signing_rust_future_cancel_i32(
        `handle`: Long,
    ): Unit = kardano_ed25519_bip32_signing.cinterop.ffi_kardano_ed25519_bip32_signing_rust_future_cancel_i32(
        `handle`,
    )
    fun ffi_kardano_ed25519_bip32_signing_rust_future_free_i32(
        `handle`: Long,
    ): Unit = kardano_ed25519_bip32_signing.cinterop.ffi_kardano_ed25519_bip32_signing_rust_future_free_i32(
        `handle`,
    )
    fun ffi_kardano_ed25519_bip32_signing_rust_future_complete_i32(
        `handle`: Long,
        uniffiCallStatus: UniffiRustCallStatus,
    ): Int = kardano_ed25519_bip32_signing.cinterop.ffi_kardano_ed25519_bip32_signing_rust_future_complete_i32(
        `handle`,
        uniffiCallStatus,
    )
    fun ffi_kardano_ed25519_bip32_signing_rust_future_poll_u64(
        `handle`: Long,
        `callback`: UniffiRustFutureContinuationCallback,
        `callbackData`: Long,
    ): Unit = kardano_ed25519_bip32_signing.cinterop.ffi_kardano_ed25519_bip32_signing_rust_future_poll_u64(
        `handle`,
        `callback`,
        `callbackData`,
    )
    fun ffi_kardano_ed25519_bip32_signing_rust_future_cancel_u64(
        `handle`: Long,
    ): Unit = kardano_ed25519_bip32_signing.cinterop.ffi_kardano_ed25519_bip32_signing_rust_future_cancel_u64(
        `handle`,
    )
    fun ffi_kardano_ed25519_bip32_signing_rust_future_free_u64(
        `handle`: Long,
    ): Unit = kardano_ed25519_bip32_signing.cinterop.ffi_kardano_ed25519_bip32_signing_rust_future_free_u64(
        `handle`,
    )
    fun ffi_kardano_ed25519_bip32_signing_rust_future_complete_u64(
        `handle`: Long,
        uniffiCallStatus: UniffiRustCallStatus,
    ): Long = kardano_ed25519_bip32_signing.cinterop.ffi_kardano_ed25519_bip32_signing_rust_future_complete_u64(
        `handle`,
        uniffiCallStatus,
    )
    fun ffi_kardano_ed25519_bip32_signing_rust_future_poll_i64(
        `handle`: Long,
        `callback`: UniffiRustFutureContinuationCallback,
        `callbackData`: Long,
    ): Unit = kardano_ed25519_bip32_signing.cinterop.ffi_kardano_ed25519_bip32_signing_rust_future_poll_i64(
        `handle`,
        `callback`,
        `callbackData`,
    )
    fun ffi_kardano_ed25519_bip32_signing_rust_future_cancel_i64(
        `handle`: Long,
    ): Unit = kardano_ed25519_bip32_signing.cinterop.ffi_kardano_ed25519_bip32_signing_rust_future_cancel_i64(
        `handle`,
    )
    fun ffi_kardano_ed25519_bip32_signing_rust_future_free_i64(
        `handle`: Long,
    ): Unit = kardano_ed25519_bip32_signing.cinterop.ffi_kardano_ed25519_bip32_signing_rust_future_free_i64(
        `handle`,
    )
    fun ffi_kardano_ed25519_bip32_signing_rust_future_complete_i64(
        `handle`: Long,
        uniffiCallStatus: UniffiRustCallStatus,
    ): Long = kardano_ed25519_bip32_signing.cinterop.ffi_kardano_ed25519_bip32_signing_rust_future_complete_i64(
        `handle`,
        uniffiCallStatus,
    )
    fun ffi_kardano_ed25519_bip32_signing_rust_future_poll_f32(
        `handle`: Long,
        `callback`: UniffiRustFutureContinuationCallback,
        `callbackData`: Long,
    ): Unit = kardano_ed25519_bip32_signing.cinterop.ffi_kardano_ed25519_bip32_signing_rust_future_poll_f32(
        `handle`,
        `callback`,
        `callbackData`,
    )
    fun ffi_kardano_ed25519_bip32_signing_rust_future_cancel_f32(
        `handle`: Long,
    ): Unit = kardano_ed25519_bip32_signing.cinterop.ffi_kardano_ed25519_bip32_signing_rust_future_cancel_f32(
        `handle`,
    )
    fun ffi_kardano_ed25519_bip32_signing_rust_future_free_f32(
        `handle`: Long,
    ): Unit = kardano_ed25519_bip32_signing.cinterop.ffi_kardano_ed25519_bip32_signing_rust_future_free_f32(
        `handle`,
    )
    fun ffi_kardano_ed25519_bip32_signing_rust_future_complete_f32(
        `handle`: Long,
        uniffiCallStatus: UniffiRustCallStatus,
    ): Float = kardano_ed25519_bip32_signing.cinterop.ffi_kardano_ed25519_bip32_signing_rust_future_complete_f32(
        `handle`,
        uniffiCallStatus,
    )
    fun ffi_kardano_ed25519_bip32_signing_rust_future_poll_f64(
        `handle`: Long,
        `callback`: UniffiRustFutureContinuationCallback,
        `callbackData`: Long,
    ): Unit = kardano_ed25519_bip32_signing.cinterop.ffi_kardano_ed25519_bip32_signing_rust_future_poll_f64(
        `handle`,
        `callback`,
        `callbackData`,
    )
    fun ffi_kardano_ed25519_bip32_signing_rust_future_cancel_f64(
        `handle`: Long,
    ): Unit = kardano_ed25519_bip32_signing.cinterop.ffi_kardano_ed25519_bip32_signing_rust_future_cancel_f64(
        `handle`,
    )
    fun ffi_kardano_ed25519_bip32_signing_rust_future_free_f64(
        `handle`: Long,
    ): Unit = kardano_ed25519_bip32_signing.cinterop.ffi_kardano_ed25519_bip32_signing_rust_future_free_f64(
        `handle`,
    )
    fun ffi_kardano_ed25519_bip32_signing_rust_future_complete_f64(
        `handle`: Long,
        uniffiCallStatus: UniffiRustCallStatus,
    ): Double = kardano_ed25519_bip32_signing.cinterop.ffi_kardano_ed25519_bip32_signing_rust_future_complete_f64(
        `handle`,
        uniffiCallStatus,
    )
    fun ffi_kardano_ed25519_bip32_signing_rust_future_poll_pointer(
        `handle`: Long,
        `callback`: UniffiRustFutureContinuationCallback,
        `callbackData`: Long,
    ): Unit = kardano_ed25519_bip32_signing.cinterop.ffi_kardano_ed25519_bip32_signing_rust_future_poll_pointer(
        `handle`,
        `callback`,
        `callbackData`,
    )
    fun ffi_kardano_ed25519_bip32_signing_rust_future_cancel_pointer(
        `handle`: Long,
    ): Unit = kardano_ed25519_bip32_signing.cinterop.ffi_kardano_ed25519_bip32_signing_rust_future_cancel_pointer(
        `handle`,
    )
    fun ffi_kardano_ed25519_bip32_signing_rust_future_free_pointer(
        `handle`: Long,
    ): Unit = kardano_ed25519_bip32_signing.cinterop.ffi_kardano_ed25519_bip32_signing_rust_future_free_pointer(
        `handle`,
    )
    fun ffi_kardano_ed25519_bip32_signing_rust_future_complete_pointer(
        `handle`: Long,
        uniffiCallStatus: UniffiRustCallStatus,
    ): Pointer? = kardano_ed25519_bip32_signing.cinterop.ffi_kardano_ed25519_bip32_signing_rust_future_complete_pointer(
        `handle`,
        uniffiCallStatus,
    )
    fun ffi_kardano_ed25519_bip32_signing_rust_future_poll_rust_buffer(
        `handle`: Long,
        `callback`: UniffiRustFutureContinuationCallback,
        `callbackData`: Long,
    ): Unit = kardano_ed25519_bip32_signing.cinterop.ffi_kardano_ed25519_bip32_signing_rust_future_poll_rust_buffer(
        `handle`,
        `callback`,
        `callbackData`,
    )
    fun ffi_kardano_ed25519_bip32_signing_rust_future_cancel_rust_buffer(
        `handle`: Long,
    ): Unit = kardano_ed25519_bip32_signing.cinterop.ffi_kardano_ed25519_bip32_signing_rust_future_cancel_rust_buffer(
        `handle`,
    )
    fun ffi_kardano_ed25519_bip32_signing_rust_future_free_rust_buffer(
        `handle`: Long,
    ): Unit = kardano_ed25519_bip32_signing.cinterop.ffi_kardano_ed25519_bip32_signing_rust_future_free_rust_buffer(
        `handle`,
    )
    fun ffi_kardano_ed25519_bip32_signing_rust_future_complete_rust_buffer(
        `handle`: Long,
        uniffiCallStatus: UniffiRustCallStatus,
    ): RustBufferByValue = kardano_ed25519_bip32_signing.cinterop.ffi_kardano_ed25519_bip32_signing_rust_future_complete_rust_buffer(
        `handle`,
        uniffiCallStatus,
    )
    fun ffi_kardano_ed25519_bip32_signing_rust_future_poll_void(
        `handle`: Long,
        `callback`: UniffiRustFutureContinuationCallback,
        `callbackData`: Long,
    ): Unit = kardano_ed25519_bip32_signing.cinterop.ffi_kardano_ed25519_bip32_signing_rust_future_poll_void(
        `handle`,
        `callback`,
        `callbackData`,
    )
    fun ffi_kardano_ed25519_bip32_signing_rust_future_cancel_void(
        `handle`: Long,
    ): Unit = kardano_ed25519_bip32_signing.cinterop.ffi_kardano_ed25519_bip32_signing_rust_future_cancel_void(
        `handle`,
    )
    fun ffi_kardano_ed25519_bip32_signing_rust_future_free_void(
        `handle`: Long,
    ): Unit = kardano_ed25519_bip32_signing.cinterop.ffi_kardano_ed25519_bip32_signing_rust_future_free_void(
        `handle`,
    )
    fun ffi_kardano_ed25519_bip32_signing_rust_future_complete_void(
        `handle`: Long,
        uniffiCallStatus: UniffiRustCallStatus,
    ): Unit = kardano_ed25519_bip32_signing.cinterop.ffi_kardano_ed25519_bip32_signing_rust_future_complete_void(
        `handle`,
        uniffiCallStatus,
    )
    fun uniffi_kardano_ed25519_bip32_signing_checksum_func_derive_xpub(
    ): Short = kardano_ed25519_bip32_signing.cinterop.uniffi_kardano_ed25519_bip32_signing_checksum_func_derive_xpub(
    )
    fun uniffi_kardano_ed25519_bip32_signing_checksum_func_sign(
    ): Short = kardano_ed25519_bip32_signing.cinterop.uniffi_kardano_ed25519_bip32_signing_checksum_func_sign(
    )
    fun uniffi_kardano_ed25519_bip32_signing_checksum_func_verify(
    ): Short = kardano_ed25519_bip32_signing.cinterop.uniffi_kardano_ed25519_bip32_signing_checksum_func_verify(
    )
    fun ffi_kardano_ed25519_bip32_signing_uniffi_contract_version(
    ): Int = kardano_ed25519_bip32_signing.cinterop.ffi_kardano_ed25519_bip32_signing_uniffi_contract_version(
    )

}

public fun uniffiEnsureInitialized() {
    UniffiLib
}

// Public interface members begin here.



public object FfiConverterBoolean: FfiConverter<Boolean, Byte> {
    override fun lift(value: Byte): Boolean {
        return value.toInt() != 0
    }

    override fun read(buf: ByteBuffer): Boolean {
        return lift(buf.get())
    }

    override fun lower(value: Boolean): Byte {
        return if (value) 1.toByte() else 0.toByte()
    }

    override fun allocationSize(value: Boolean): ULong = 1UL

    override fun write(value: Boolean, buf: ByteBuffer) {
        buf.put(lower(value))
    }
}


public object FfiConverterString: FfiConverter<String, RustBufferByValue> {
    // Note: we don't inherit from FfiConverterRustBuffer, because we use a
    // special encoding when lowering/lifting.  We can use `RustBuffer.len` to
    // store our length and avoid writing it out to the buffer.
    override fun lift(value: RustBufferByValue): String {
        try {
            require(value.len <= Int.MAX_VALUE) {
        val length = value.len
        "cannot handle RustBuffer longer than Int.MAX_VALUE bytes: length is $length"
    }
            val byteArr =  value.asByteBuffer()!!.get(value.len.toInt())
            return byteArr.decodeToString()
        } finally {
            RustBufferHelper.free(value)
        }
    }

    override fun read(buf: ByteBuffer): String {
        val len = buf.getInt()
        val byteArr = buf.get(len)
        return byteArr.decodeToString()
    }

    override fun lower(value: String): RustBufferByValue {
        // TODO: prevent allocating a new byte array here
        val encoded = value.encodeToByteArray(throwOnInvalidSequence = true)
        return RustBufferHelper.allocValue(encoded.size.toULong()).apply {
            asByteBuffer()!!.put(encoded)
        }
    }

    // We aren't sure exactly how many bytes our string will be once it's UTF-8
    // encoded.  Allocate 3 bytes per UTF-16 code unit which will always be
    // enough.
    override fun allocationSize(value: String): ULong {
        val sizeForLength = 4UL
        val sizeForString = value.length.toULong() * 3UL
        return sizeForLength + sizeForString
    }

    override fun write(value: String, buf: ByteBuffer) {
        // TODO: prevent allocating a new byte array here
        val encoded = value.encodeToByteArray(throwOnInvalidSequence = true)
        buf.putInt(encoded.size)
        buf.put(encoded)
    }
}


public object FfiConverterByteArray: FfiConverterRustBuffer<ByteArray> {
    override fun read(buf: ByteBuffer): ByteArray {
        val len = buf.getInt()
        val byteArr = buf.get(len)
        return byteArr
    }
    override fun allocationSize(value: ByteArray): ULong {
        return 4UL + value.size.toULong()
    }
    override fun write(value: ByteArray, buf: ByteBuffer) {
        buf.putInt(value.size)
        buf.put(value)
    }
}




public object SigningBackendExceptionErrorHandler : UniffiRustCallStatusErrorHandler<SigningBackendException> {
    override fun lift(errorBuf: RustBufferByValue): SigningBackendException = FfiConverterTypeSigningBackendError.lift(errorBuf)
}

public object FfiConverterTypeSigningBackendError : FfiConverterRustBuffer<SigningBackendException> {
    override fun read(buf: ByteBuffer): SigningBackendException {
        return when (buf.getInt()) {
            1 -> SigningBackendException.InvalidExtendedPrivateKey()
            2 -> SigningBackendException.InvalidExtendedPublicKey()
            3 -> SigningBackendException.InvalidSignature()
            else -> throw RuntimeException("invalid error enum value, something is very wrong!!")
        }
    }

    override fun allocationSize(value: SigningBackendException): ULong {
        return when (value) {
            is SigningBackendException.InvalidExtendedPrivateKey -> (
                // Add the size for the Int that specifies the variant plus the size needed for all fields
                4UL
            )
            is SigningBackendException.InvalidExtendedPublicKey -> (
                // Add the size for the Int that specifies the variant plus the size needed for all fields
                4UL
            )
            is SigningBackendException.InvalidSignature -> (
                // Add the size for the Int that specifies the variant plus the size needed for all fields
                4UL
            )
        }
    }

    override fun write(value: SigningBackendException, buf: ByteBuffer) {
        when (value) {
            is SigningBackendException.InvalidExtendedPrivateKey -> {
                buf.putInt(1)
                Unit
            }
            is SigningBackendException.InvalidExtendedPublicKey -> {
                buf.putInt(2)
                Unit
            }
            is SigningBackendException.InvalidSignature -> {
                buf.putInt(3)
                Unit
            }
        }.let { /* this makes the `when` an expression, which ensures it is exhaustive */ }
    }
}


/**
 * Derives the extended public key from an extended private key `xprv`, delegating to
 * `ed25519_bip32::XPrv::public`. Exposed only so backend tests can exercise `verify()` without
 * hardcoding a second key fixture; this is derivation — the same operation the shipped
 * `bip32-ed25519:1.8.8` wrapper already exposes and verifies (ADR-0016 §1) — not new
 * cryptographic logic.
 */
@Throws(SigningBackendException::class)
public actual fun `deriveXpub`(`xprv`: kotlin.ByteArray): kotlin.ByteArray {
    return FfiConverterByteArray.lift(uniffiRustCallWithError(SigningBackendExceptionErrorHandler) { uniffiRustCallStatus ->
        UniffiLib.uniffi_kardano_ed25519_bip32_signing_fn_func_derive_xpub(
            FfiConverterByteArray.lower(`xprv`),
            uniffiRustCallStatus,
        )
    })
}

/**
 * Signs `message` with the Cardano extended Ed25519-BIP32 private key `xprv` (96 bytes),
 * delegating to `ed25519_bip32::XPrv::sign`. Returns the raw 64-byte signature. No handwritten
 * signing math.
 */
@Throws(SigningBackendException::class)
public actual fun `sign`(`xprv`: kotlin.ByteArray, `message`: kotlin.ByteArray): kotlin.ByteArray {
    return FfiConverterByteArray.lift(uniffiRustCallWithError(SigningBackendExceptionErrorHandler) { uniffiRustCallStatus ->
        UniffiLib.uniffi_kardano_ed25519_bip32_signing_fn_func_sign(
            FfiConverterByteArray.lower(`xprv`),
            FfiConverterByteArray.lower(`message`),
            uniffiRustCallStatus,
        )
    })
}

/**
 * Verifies `signature` over `message` against the Cardano extended Ed25519-BIP32 public key
 * `xpub` (64 bytes), delegating to `ed25519_bip32::XPub::verify`. No handwritten verification
 * math.
 */
@Throws(SigningBackendException::class)
public actual fun `verify`(`xpub`: kotlin.ByteArray, `message`: kotlin.ByteArray, `signature`: kotlin.ByteArray): kotlin.Boolean {
    return FfiConverterBoolean.lift(uniffiRustCallWithError(SigningBackendExceptionErrorHandler) { uniffiRustCallStatus ->
        UniffiLib.uniffi_kardano_ed25519_bip32_signing_fn_func_verify(
            FfiConverterByteArray.lower(`xpub`),
            FfiConverterByteArray.lower(`message`),
            FfiConverterByteArray.lower(`signature`),
            uniffiRustCallStatus,
        )
    })
}


// Async support