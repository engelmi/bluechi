project(
  'hirte',
  'c',
  version: '0.0.1',
  license: 'GPL-2.0-or-later',
  default_options: [
    'c_std=gnu17',     # Adds "-std=gnu17".  Includes GNU 17 extensions.
    'warning_level=2', # Adds "-Wextra".  Enables additional warnings. 
    'debug=true',      # Adds "-g".  Object files include debugging symbols.
    'werror=true'      # Adds "-Werror".  Treat warnings as errors.
  ]
)

# Enable GNU extensions.
add_global_arguments('-D_GNU_SOURCE', language : 'c')

# Link with systemd shared library.
systemd_dep = dependency('libsystemd')

# Subdirectory for the shared library.
subdir('src/libhirte')

# build each binary
subdir('src/orch')
subdir('src/node')
subdir('src/client')