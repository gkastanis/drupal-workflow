# Extended Test Patterns

Advanced test patterns for complex Drupal verification scenarios.

## Plugin Verification

Test that a plugin exists and can be instantiated:

```php
$result = [
  "test_type" => "plugin",
  "target" => "PLUGIN_TYPE:PLUGIN_ID",
  "timestamp" => date("c"),
  "status" => "pass",
  "checks" => [],
];

$manager = Drupal::service("plugin.manager.PLUGIN_TYPE");

// Check plugin definition exists
$definitions = $manager->getDefinitions();
if (!isset($definitions["PLUGIN_ID"])) {
  $result["status"] = "fail";
  $result["checks"]["definition"] = ["status" => "fail", "message" => "Plugin not defined"];
  echo json_encode($result, JSON_PRETTY_PRINT);
  return;
}

$result["checks"]["definition"] = [
  "status" => "pass",
  "message" => "Plugin defined",
  "data" => ["class" => $definitions["PLUGIN_ID"]["class"]],
];

// Try to create instance
try {
  $instance = $manager->createInstance("PLUGIN_ID", []);
  $result["checks"]["instantiation"] = ["status" => "pass", "message" => "Plugin instantiated"];
} catch (Exception $e) {
  $result["status"] = "fail";
  $result["checks"]["instantiation"] = ["status" => "fail", "message" => $e->getMessage()];
}

echo json_encode($result, JSON_PRETTY_PRINT);
```

## Block Plugin Test

```php
$result = [
  "test_type" => "plugin",
  "target" => "block:BLOCK_ID",
  "timestamp" => date("c"),
  "status" => "pass",
  "checks" => [],
];

$manager = Drupal::service("plugin.manager.block");

try {
  $instance = $manager->createInstance("BLOCK_ID", []);
  $build = $instance->build();

  $result["checks"]["build"] = [
    "status" => !empty($build) ? "pass" : "fail",
    "message" => !empty($build) ? "Block builds content" : "Block returns empty",
    "data" => ["render_type" => isset($build["#type"]) ? $build["#type"] : "custom"],
  ];
} catch (Exception $e) {
  $result["status"] = "fail";
  $result["checks"]["build"] = ["status" => "fail", "message" => $e->getMessage()];
}

echo json_encode($result, JSON_PRETTY_PRINT);
```

## Form Verification

Test that a form class exists and can build:

```php
$result = [
  "test_type" => "form",
  "target" => "FORM_CLASS",
  "timestamp" => date("c"),
  "status" => "pass",
  "checks" => [],
];

$form_class = "\\Drupal\\MODULE\\Form\\FORM_CLASS";

if (!class_exists($form_class)) {
  $result["status"] = "fail";
  $result["checks"]["class"] = ["status" => "fail", "message" => "Form class not found"];
  echo json_encode($result, JSON_PRETTY_PRINT);
  return;
}

$result["checks"]["class"] = ["status" => "pass", "message" => "Form class exists"];

// Check form ID
$form = Drupal::classResolver()->getInstanceFromDefinition($form_class);
$form_id = $form->getFormId();
$result["checks"]["form_id"] = [
  "status" => "pass",
  "message" => "Form ID: $form_id",
  "data" => ["form_id" => $form_id],
];

// Try to build form
try {
  $form_state = new \Drupal\Core\Form\FormState();
  $form_array = Drupal::formBuilder()->buildForm($form_class, $form_state);
  $elements = array_filter(array_keys($form_array), fn($k) => !str_starts_with($k, "#"));

  $result["checks"]["build"] = [
    "status" => "pass",
    "message" => count($elements) . " form elements",
    "data" => ["elements" => array_slice($elements, 0, 10)],
  ];
} catch (Exception $e) {
  $result["status"] = "fail";
  $result["checks"]["build"] = ["status" => "fail", "message" => $e->getMessage()];
}

echo json_encode($result, JSON_PRETTY_PRINT);
```

## Event Subscriber Verification

Test that an event subscriber is registered:

```php
$result = [
  "test_type" => "event_subscriber",
  "target" => "EVENT_NAME",
  "timestamp" => date("c"),
  "status" => "pass",
  "checks" => [],
];

$dispatcher = Drupal::service("event_dispatcher");
$listeners = $dispatcher->getListeners("EVENT_NAME");

if (empty($listeners)) {
  $result["status"] = "fail";
  $result["checks"]["listeners"] = ["status" => "fail", "message" => "No listeners for event"];
} else {
  $listener_info = [];
  foreach ($listeners as $listener) {
    if (is_array($listener)) {
      $listener_info[] = get_class($listener[0]) . "::" . $listener[1];
    }
  }
  $result["checks"]["listeners"] = [
    "status" => "pass",
    "message" => count($listeners) . " listener(s)",
    "data" => ["listeners" => $listener_info],
  ];
}

// Check specific subscriber class
$subscriber_class = "Drupal\\MODULE\\EventSubscriber\\CLASS_NAME";
$found = false;
foreach ($listeners as $listener) {
  if (is_array($listener) && get_class($listener[0]) === $subscriber_class) {
    $found = true;
    break;
  }
}

$result["checks"]["target_subscriber"] = [
  "status" => $found ? "pass" : "fail",
  "message" => $found ? "Subscriber registered" : "Subscriber not found",
];

if (!$found) {
  $result["status"] = "fail";
}

echo json_encode($result, JSON_PRETTY_PRINT);
```

## Queue Worker Test

Test queue worker plugin:

```php
$result = [
  "test_type" => "plugin",
  "target" => "queue_worker:QUEUE_ID",
  "timestamp" => date("c"),
  "status" => "pass",
  "checks" => [],
];

$manager = Drupal::service("plugin.manager.queue_worker");
$definitions = $manager->getDefinitions();

if (!isset($definitions["QUEUE_ID"])) {
  $result["status"] = "fail";
  $result["checks"]["definition"] = ["status" => "fail", "message" => "Queue worker not defined"];
  echo json_encode($result, JSON_PRETTY_PRINT);
  return;
}

$definition = $definitions["QUEUE_ID"];
$result["checks"]["definition"] = [
  "status" => "pass",
  "message" => "Queue worker defined",
  "data" => [
    "title" => (string) $definition["title"],
    "cron" => $definition["cron"] ?? null,
  ],
];

// Check queue exists
$queue = Drupal::queue("QUEUE_ID");
$result["checks"]["queue"] = [
  "status" => "pass",
  "message" => "Queue accessible",
  "data" => ["items" => $queue->numberOfItems()],
];

echo json_encode($result, JSON_PRETTY_PRINT);
```

## Migration Verification

Test migration definition:

```php
$result = [
  "test_type" => "migration",
  "target" => "MIGRATION_ID",
  "timestamp" => date("c"),
  "status" => "pass",
  "checks" => [],
];

$manager = Drupal::service("plugin.manager.migration");

try {
  $migration = $manager->createInstance("MIGRATION_ID");

  $result["checks"]["definition"] = [
    "status" => "pass",
    "message" => "Migration defined",
    "data" => [
      "label" => $migration->label(),
      "source_plugin" => $migration->getSourcePlugin()->getPluginId(),
      "destination_plugin" => $migration->getDestinationPlugin()->getPluginId(),
    ],
  ];

  // Check source
  try {
    $source = $migration->getSourcePlugin();
    $source->rewind();
    $count = $source->count();
    $result["checks"]["source"] = [
      "status" => "pass",
      "message" => "Source accessible",
      "data" => ["count" => $count],
    ];
  } catch (Exception $e) {
    $result["checks"]["source"] = ["status" => "fail", "message" => $e->getMessage()];
    $result["status"] = "fail";
  }

} catch (Exception $e) {
  $result["status"] = "fail";
  $result["checks"]["definition"] = ["status" => "fail", "message" => $e->getMessage()];
}

echo json_encode($result, JSON_PRETTY_PRINT);
```

## REST Resource Test

Test REST resource plugin:

```php
$result = [
  "test_type" => "plugin",
  "target" => "rest_resource:RESOURCE_ID",
  "timestamp" => date("c"),
  "status" => "pass",
  "checks" => [],
];

$manager = Drupal::service("plugin.manager.rest");
$definitions = $manager->getDefinitions();

if (!isset($definitions["RESOURCE_ID"])) {
  $result["status"] = "fail";
  $result["checks"]["definition"] = ["status" => "fail", "message" => "REST resource not defined"];
  echo json_encode($result, JSON_PRETTY_PRINT);
  return;
}

$definition = $definitions["RESOURCE_ID"];
$result["checks"]["definition"] = [
  "status" => "pass",
  "message" => "REST resource defined",
  "data" => [
    "label" => (string) $definition["label"],
    "uri_paths" => $definition["uri_paths"] ?? [],
  ],
];

// Check REST config
$config = Drupal::config("rest.resource.RESOURCE_ID");
if ($config->isNew()) {
  $result["checks"]["config"] = ["status" => "skip", "message" => "REST resource not configured (may be OK)"];
} else {
  $result["checks"]["config"] = [
    "status" => "pass",
    "message" => "REST resource configured",
    "data" => ["methods" => array_keys($config->get("configuration") ?? [])],
  ];
}

echo json_encode($result, JSON_PRETTY_PRINT);
```

## Verbose Output Pattern

When verbose output is requested, include timing and trace:

```php
$verbose = true; // Set based on request
$start = microtime(true);
$trace = [];

// ... perform checks, adding to $trace ...
$trace[] = ["action" => "service_lookup", "time" => microtime(true) - $start];

if ($verbose) {
  $result["verbose"] = [
    "execution_time_ms" => round((microtime(true) - $start) * 1000, 2),
    "trace" => $trace,
    "memory_peak" => memory_get_peak_usage(true),
  ];
}
```

## Batch Test Pattern

For testing batch operations:

```php
$result = [
  "test_type" => "batch",
  "target" => "BATCH_OPERATION",
  "timestamp" => date("c"),
  "status" => "pass",
  "checks" => [],
];

// Test batch callback exists
$callback = "MODULE_batch_callback";
if (function_exists($callback)) {
  $result["checks"]["callback"] = ["status" => "pass", "message" => "Batch callback exists"];
} else {
  $result["status"] = "fail";
  $result["checks"]["callback"] = ["status" => "fail", "message" => "Batch callback not found"];
}

// Test batch setup
$batch = [
  "operations" => [
    [$callback, [["test_item"]]],
  ],
  "finished" => "MODULE_batch_finished",
];

$result["checks"]["definition"] = [
  "status" => "pass",
  "message" => "Batch definition valid",
  "data" => ["operations" => count($batch["operations"])],
];

echo json_encode($result, JSON_PRETTY_PRINT);
```
