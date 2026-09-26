#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#endif
#include <curl/curl.h>
#include <openssl/ssl.h>
#include <cstring>
#include <zlib.h>

extern "C"
#ifdef _WIN32
__declspec(dllexport)
#else
__attribute__((visibility("default")))
#endif
int echhttp_dependency_check() {
  SSL_CTX *context = SSL_CTX_new(TLS_method());
  if (!context) return 1;
  SSL *ssl = SSL_new(context);
  if (!ssl) { SSL_CTX_free(context); return 2; }
  SSL_set_reject_unusable_ech_config(ssl, 1);
  SSL_free(ssl);
  SSL_CTX_free(context);
  const auto *info = curl_version_info(CURLVERSION_NOW);
  if (!info || !info->ssl_version || !std::strstr(info->ssl_version, "BoringSSL")) return 3;
  if (!(info->features & CURL_VERSION_LIBZ) || !info->libz_version ||
      std::strcmp(info->libz_version, ZLIB_VERSION)) return 5;
  const unsigned char compressed[] = {31, 139, 8, 0, 0, 0, 0, 0, 2, 255, 75, 77, 206, 136, 207, 40, 41, 41, 80, 72, 175, 202, 44, 0, 0, 74, 210, 164, 231, 13, 0, 0, 0};
  unsigned char output[32] = {};
  z_stream stream = {};
  if (inflateInit2(&stream, MAX_WBITS + 16) != Z_OK) return 6;
  stream.next_in = const_cast<Bytef *>(compressed);
  stream.avail_in = sizeof(compressed);
  stream.next_out = output;
  stream.avail_out = sizeof(output);
  const int result = inflate(&stream, Z_FINISH);
  const bool decoded = result == Z_STREAM_END && stream.total_out == 13 &&
      !std::memcmp(output, "ech_http gzip", 13);
  inflateEnd(&stream);
  if (!decoded) return 7;
  if (info->feature_names) {
    for (const char *const *feature = info->feature_names; *feature; ++feature) {
      if (!std::strcmp(*feature, "ECH")) return 0;
    }
  }
  return 4;
}

#ifdef EH_PROBE_EXECUTABLE
int main() { return echhttp_dependency_check(); }
#endif
