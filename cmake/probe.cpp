#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#endif
#include <curl/curl.h>
#include <openssl/ssl.h>
#include <cstring>

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
