import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from ble_memory import configure_queues, configure_stack, install


class QueueConfigurationTests(unittest.TestCase):
    SOURCE = ('queue_ = xQueueCreate(16, sizeof(QueueMessage));\n'
              'overflowQueue_ = xQueueCreate(16, sizeof(QueueMessage));\n'
              'return xQueueSend(queue_, &message, 0);\n')

    def test_preserves_message_size_and_saturation_behavior(self):
        configured = configure_queues(self.SOURCE, 4)
        self.assertEqual(configured.replace('xQueueCreate(4,', 'xQueueCreate(16,'), self.SOURCE)

    def test_rejects_dependency_drift_and_invalid_depth(self):
        with self.assertRaises(ValueError):
            configure_queues(self.SOURCE.replace('16,', '8,'), 4)
        for depth in (0, 3, 17, True):
            with self.assertRaises(ValueError):
                configure_queues(self.SOURCE, depth)

    def test_task_stack_configuration_preserves_entry_priority_and_handle(self):
        source = 'xTaskCreate(taskEntry, "rad-ble-v1", 12288, this, 2, &taskHandle)'
        self.assertEqual(configure_stack(source, 8192).replace('8192', '12288'), source)
        for size in (0, 8191, 12289, True):
            with self.assertRaises(ValueError):
                configure_stack(source, size)
        with self.assertRaises(ValueError):
            configure_stack(source.replace('12288', '4096'), 8192)

    def test_variant_node_uses_original_source_without_mutating_dependency(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'dependency' / 'RadBle.cpp'
            source.parent.mkdir()
            source.write_text(self.SOURCE)

            class Environment(dict):
                def GetProjectOption(self, key, default):
                    return '4' if key == 'custom_radble_queue_depth' else default
                def subst(self, value): return str(root / 'build')
                def AddBuildMiddleware(self, callback, pattern): self.callback = callback
                def Object(self, source, **options):
                    return [SimpleNamespace(source=source, options=options)]

            env = Environment(CPPPATH=['existing-include'])
            install(env)
            node = SimpleNamespace(srcnode=lambda: SimpleNamespace(get_abspath=lambda: str(source)))
            generated_node = env.callback(env, node)
            generated, options = generated_node.source, generated_node.options
            self.assertEqual(source.read_text(), self.SOURCE)
            self.assertEqual(Path(generated).read_text(), configure_queues(self.SOURCE, 4))
            self.assertEqual(options['CPPPATH'], ['existing-include', str(source.parent)])


if __name__ == '__main__':
    unittest.main()
