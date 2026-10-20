"""Omit unused Arduino 2 TLS error text when its error logging is disabled."""
from pathlib import Path


def guard_error_strings(source):
    original = """#ifdef MBEDTLS_ERROR_C
    char error_buf[100];
    mbedtls_strerror(err, error_buf, 100);
    log_e("[%s():%d]: (%d) %s", function, line, err, error_buf);"""
    if source.count(original) != 1:
        raise ValueError('Pinned Arduino TLS error logger changed; review required')
    return source.replace(original, original.replace(
        '#ifdef MBEDTLS_ERROR_C',
        '#if defined(MBEDTLS_ERROR_C) && ARDUHAL_LOG_LEVEL >= ARDUHAL_LOG_LEVEL_ERROR'))


def install(env):
    if env.GetProjectOption('custom_omit_unused_tls_error_text', 'no') != 'yes':
        return

    def configure_node(build_env, node):
        original = Path(node.srcnode().get_abspath())
        source = guard_error_strings(original.read_text(encoding='utf-8'))
        destination = Path(build_env.subst('$BUILD_DIR')) / 'configured-tls-log' / 'ssl_client.cpp'
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists() or destination.read_text(encoding='utf-8') != source:
            destination.write_text(source, encoding='utf-8', newline='\n')
        return build_env.Object(str(destination),
                                CPPPATH=list(build_env.get('CPPPATH', [])) + [str(original.parent)])[0]

    env.AddBuildMiddleware(configure_node, '*/WiFiClientSecure/src/ssl_client.cpp')
