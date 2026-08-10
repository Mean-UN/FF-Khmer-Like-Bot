# -*- coding: utf-8 -*-
# Generated-compatible protobuf module for MajorLoginReq.proto.
"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pb2 as _descriptor_pb2
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder

_sym_db = _symbol_database.Default()


def _field(message, name, number, field_type, type_name=None):
    f = message.field.add()
    f.name = name
    f.number = number
    f.label = _descriptor_pb2.FieldDescriptorProto.LABEL_OPTIONAL
    f.type = field_type
    if type_name:
        f.type_name = type_name


_fd = _descriptor_pb2.FileDescriptorProto()
_fd.name = "MajorLoginReq.proto"
_fd.syntax = "proto3"

_major = _fd.message_type.add()
_major.name = "MajorLogin"
_field(_major, "event_time", 3, _descriptor_pb2.FieldDescriptorProto.TYPE_STRING)
_field(_major, "game_name", 4, _descriptor_pb2.FieldDescriptorProto.TYPE_STRING)
_field(_major, "platform_id", 5, _descriptor_pb2.FieldDescriptorProto.TYPE_INT32)
_field(_major, "client_version", 7, _descriptor_pb2.FieldDescriptorProto.TYPE_STRING)
_field(_major, "system_software", 8, _descriptor_pb2.FieldDescriptorProto.TYPE_STRING)
_field(_major, "system_hardware", 9, _descriptor_pb2.FieldDescriptorProto.TYPE_STRING)
_field(_major, "telecom_operator", 10, _descriptor_pb2.FieldDescriptorProto.TYPE_STRING)
_field(_major, "network_type", 11, _descriptor_pb2.FieldDescriptorProto.TYPE_STRING)
_field(_major, "screen_width", 12, _descriptor_pb2.FieldDescriptorProto.TYPE_UINT32)
_field(_major, "screen_height", 13, _descriptor_pb2.FieldDescriptorProto.TYPE_UINT32)
_field(_major, "screen_dpi", 14, _descriptor_pb2.FieldDescriptorProto.TYPE_STRING)
_field(_major, "processor_details", 15, _descriptor_pb2.FieldDescriptorProto.TYPE_STRING)
_field(_major, "memory", 16, _descriptor_pb2.FieldDescriptorProto.TYPE_UINT32)
_field(_major, "gpu_renderer", 17, _descriptor_pb2.FieldDescriptorProto.TYPE_STRING)
_field(_major, "gpu_version", 18, _descriptor_pb2.FieldDescriptorProto.TYPE_STRING)
_field(_major, "unique_device_id", 19, _descriptor_pb2.FieldDescriptorProto.TYPE_STRING)
_field(_major, "client_ip", 20, _descriptor_pb2.FieldDescriptorProto.TYPE_STRING)
_field(_major, "language", 21, _descriptor_pb2.FieldDescriptorProto.TYPE_STRING)
_field(_major, "open_id", 22, _descriptor_pb2.FieldDescriptorProto.TYPE_STRING)
_field(_major, "open_id_type", 23, _descriptor_pb2.FieldDescriptorProto.TYPE_STRING)
_field(_major, "device_type", 24, _descriptor_pb2.FieldDescriptorProto.TYPE_STRING)
_field(_major, "memory_available", 25, _descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE, ".GameSecurity")
_field(_major, "access_token", 29, _descriptor_pb2.FieldDescriptorProto.TYPE_STRING)
_field(_major, "platform_sdk_id", 30, _descriptor_pb2.FieldDescriptorProto.TYPE_INT32)
_field(_major, "network_operator_a", 41, _descriptor_pb2.FieldDescriptorProto.TYPE_STRING)
_field(_major, "network_type_a", 42, _descriptor_pb2.FieldDescriptorProto.TYPE_STRING)
_field(_major, "client_using_version", 57, _descriptor_pb2.FieldDescriptorProto.TYPE_STRING)
_field(_major, "external_storage_total", 60, _descriptor_pb2.FieldDescriptorProto.TYPE_INT32)
_field(_major, "external_storage_available", 61, _descriptor_pb2.FieldDescriptorProto.TYPE_INT32)
_field(_major, "internal_storage_total", 62, _descriptor_pb2.FieldDescriptorProto.TYPE_INT32)
_field(_major, "internal_storage_available", 63, _descriptor_pb2.FieldDescriptorProto.TYPE_INT32)
_field(_major, "game_disk_storage_available", 64, _descriptor_pb2.FieldDescriptorProto.TYPE_INT32)
_field(_major, "game_disk_storage_total", 65, _descriptor_pb2.FieldDescriptorProto.TYPE_INT32)
_field(_major, "external_sdcard_avail_storage", 66, _descriptor_pb2.FieldDescriptorProto.TYPE_INT32)
_field(_major, "external_sdcard_total_storage", 67, _descriptor_pb2.FieldDescriptorProto.TYPE_INT32)
_field(_major, "login_by", 73, _descriptor_pb2.FieldDescriptorProto.TYPE_INT32)
_field(_major, "library_path", 74, _descriptor_pb2.FieldDescriptorProto.TYPE_STRING)
_field(_major, "reg_avatar", 76, _descriptor_pb2.FieldDescriptorProto.TYPE_INT32)
_field(_major, "library_token", 77, _descriptor_pb2.FieldDescriptorProto.TYPE_STRING)
_field(_major, "channel_type", 78, _descriptor_pb2.FieldDescriptorProto.TYPE_INT32)
_field(_major, "cpu_type", 79, _descriptor_pb2.FieldDescriptorProto.TYPE_INT32)
_field(_major, "cpu_architecture", 81, _descriptor_pb2.FieldDescriptorProto.TYPE_STRING)
_field(_major, "client_version_code", 83, _descriptor_pb2.FieldDescriptorProto.TYPE_STRING)
_field(_major, "graphics_api", 86, _descriptor_pb2.FieldDescriptorProto.TYPE_STRING)
_field(_major, "supported_astc_bitset", 87, _descriptor_pb2.FieldDescriptorProto.TYPE_UINT32)
_field(_major, "login_open_id_type", 88, _descriptor_pb2.FieldDescriptorProto.TYPE_INT32)
_field(_major, "analytics_detail", 89, _descriptor_pb2.FieldDescriptorProto.TYPE_BYTES)
_field(_major, "loading_time", 92, _descriptor_pb2.FieldDescriptorProto.TYPE_UINT32)
_field(_major, "release_channel", 93, _descriptor_pb2.FieldDescriptorProto.TYPE_STRING)
_field(_major, "extra_info", 94, _descriptor_pb2.FieldDescriptorProto.TYPE_STRING)
_field(_major, "android_engine_init_flag", 95, _descriptor_pb2.FieldDescriptorProto.TYPE_UINT32)
_field(_major, "if_push", 97, _descriptor_pb2.FieldDescriptorProto.TYPE_INT32)
_field(_major, "is_vpn", 98, _descriptor_pb2.FieldDescriptorProto.TYPE_INT32)
_field(_major, "origin_platform_type", 99, _descriptor_pb2.FieldDescriptorProto.TYPE_STRING)
_field(_major, "primary_platform_type", 100, _descriptor_pb2.FieldDescriptorProto.TYPE_STRING)

_security = _fd.message_type.add()
_security.name = "GameSecurity"
_field(_security, "version", 6, _descriptor_pb2.FieldDescriptorProto.TYPE_INT32)
_field(_security, "hidden_value", 8, _descriptor_pb2.FieldDescriptorProto.TYPE_UINT64)

DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(_fd.SerializeToString())

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, "MajorLoginReq_pb2", _globals)
if _descriptor._USE_C_DESCRIPTORS == False:
    DESCRIPTOR._options = None
# @@protoc_insertion_point(module_scope)
