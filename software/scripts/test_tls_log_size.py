import unittest
from tls_log_size import guard_error_strings


SOURCE = '''static int _handle_error(int err, const char * function, int line)
{
#ifdef MBEDTLS_ERROR_C
    char error_buf[100];
    mbedtls_strerror(err, error_buf, 100);
    log_e("[%s():%d]: (%d) %s", function, line, err, error_buf);
#else
    log_e("[%s():%d]: code %d", function, line, err);
#endif
    return err;
}
'''


class TlsLogSizeTests(unittest.TestCase):
    def test_changes_only_compilation_guard_preserving_error_and_tls_behavior(self):
        result = guard_error_strings(SOURCE)
        self.assertEqual(result.replace(
            '#if defined(MBEDTLS_ERROR_C) && ARDUHAL_LOG_LEVEL >= ARDUHAL_LOG_LEVEL_ERROR',
            '#ifdef MBEDTLS_ERROR_C'), SOURCE)

    def test_refuses_changed_sdk(self):
        with self.assertRaises(ValueError):
            guard_error_strings(SOURCE.replace('error_buf[100]', 'error_buf[200]'))

    def test_refuses_ambiguous_sdk(self):
        with self.assertRaises(ValueError):
            guard_error_strings(SOURCE + SOURCE)


if __name__ == '__main__':
    unittest.main()
