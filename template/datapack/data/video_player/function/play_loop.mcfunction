# play video
execute store result storage video_player:frame_control frame int 1 run scoreboard players get frame video_player
execute as @e[type=text_display,tag=frame] at @s run function video_player:play_frame with storage video_player:frame_control

# play sound
scoreboard players operation audio_part video_player = frame video_player
scoreboard players operation audio_part video_player %= audio_segment video_player
execute if score audio_part video_player matches 0 run function video_player:play_sound_calc

# play subtitle
execute as @e[type=text_display,tag=subtitle] run function video_player:subtitle with storage video_player:frame_control

execute if score frame video_player > end_frame video_player run function video_player:stop
scoreboard players add frame video_player 1
