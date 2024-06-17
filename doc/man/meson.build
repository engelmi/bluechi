#
# Copyright Contributors to the Eclipse BlueChi project
#
# SPDX-License-Identifier: LGPL-2.1-or-later

want_man = get_option('with_man_pages')
md2man = find_program('go-md2man', required : false)
if want_man and not md2man.found()
  message('go-md2man not found, man page generation disabled automatically')
endif
want_man = want_man and md2man.found()

mans = {
  'bluechi-controller': [
    'bluechi-controller.1',
    'bluechi-controller.conf.5',
    'bluechi-controller-selinux.8',
  ],
  'bluechi-agent': [
    'bluechi-agent.1',
    'bluechi-proxy.1',
    'bluechi-agent.conf.5',
    'bluechi-agent-selinux.8',
  ],
  'bluechictl': [
    'bluechictl.1',
  ],
}

if want_man
  foreach tag, man_files : mans
    foreach man : man_files
      message(man.substring(-1, 128) != '8')
      if man.substring(-1, 128) != '8' or get_option('with_selinux')
        custom_target(
          man,
          input : [man + '.md'],
          output : [man],
          command : [
            md2man,
            '-in', '@INPUT@',
            '-out', '@OUTPUT@',
          ],
          build_by_default : true,
          install : true,
          install_dir : get_option('mandir') / ('man' + man.substring(-1, 128)),
          install_tag: tag,
        )
      endif
    endforeach
  endforeach
endif
