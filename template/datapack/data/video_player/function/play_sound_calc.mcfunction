scoreboard players operation audio_part video_player = frame video_player
scoreboard players operation audio_part video_player /= audio_segment video_player
execute store result storage video_player:audio_control part int 1 run scoreboard players get audio_part video_player
execute as @e[type=text_display,tag=frame,limit=1] at @s run function video_player:play_sound with storage video_player:audio_control
