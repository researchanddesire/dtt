"""Configure the pinned RadBLE queue storage without changing its protocol."""
from pathlib import Path


def configure_queues(source, depth):
    if type(depth) is not int or not 4 <= depth <= 16:
        raise ValueError('RadBLE queue depth must be between 4 and 16')
    for queue in ('queue_', 'overflowQueue_'):
        original = f'{queue} = xQueueCreate(16, sizeof(QueueMessage));'
        if source.count(original) != 1:
            raise ValueError('Pinned RadBLE queue allocation changed; review required')
        source = source.replace(original, f'{queue} = xQueueCreate({depth}, sizeof(QueueMessage));')
    return source


def install(env):
    depth = env.GetProjectOption('custom_radble_queue_depth', None)
    if depth is None:
        return
    depth = int(depth)
    stack_bytes = env.GetProjectOption('custom_radble_stack_bytes', None)
    if stack_bytes is not None:
        stack_bytes = int(stack_bytes)

    def configure_node(build_env, node):
        original = Path(node.srcnode().get_abspath())
        source = configure_queues(original.read_text(encoding='utf-8'), depth)
        if stack_bytes is not None:
            source = configure_stack(source, stack_bytes)
        destination = Path(build_env.subst('$BUILD_DIR')) / 'configured-radble' / 'RadBle.cpp'
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists() or destination.read_text(encoding='utf-8') != source:
            destination.write_text(source, encoding='utf-8', newline='\n')
        # Keep the downloaded dependency untouched and retain its own headers.
        # Later ESP-IDF middleware inspects each node's source; return the single
        # Object node, not SCons' NodeList wrapper.
        return build_env.Object(str(destination),
                                CPPPATH=list(build_env.get('CPPPATH', [])) + [str(original.parent)])[0]

    env.AddBuildMiddleware(configure_node, '*/RadBLE/src/RadBle.cpp')


def configure_stack(source, size):
    if type(size) is not int or not 8192 <= size <= 12288:
        raise ValueError('RadBLE stack must remain between 8 and 12 KiB')
    original = 'xTaskCreate(taskEntry, "rad-ble-v1", 12288, this, 2, &taskHandle)'
    if source.count(original) != 1:
        raise ValueError('Pinned RadBLE task allocation changed; review required')
    return source.replace(original, original.replace('12288', str(size)))
