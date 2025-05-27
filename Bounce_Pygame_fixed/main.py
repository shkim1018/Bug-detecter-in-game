import pygame as pg
import random
from settings import *
from bug_settings import *
from sprites import *
import os
import sys
import math
from Camera import *
from buttons import *
import logging
from datetime import datetime
import numpy as np

class Game:
    def __init__(self, model=None, render_mode=True, log_mode=False, bug_mode=False, control_mode="human", train_mode=False):
        pg.init()
        # pg.mixer.init() # We might not use the audio.
        self.model = model
        self.log_mode = log_mode
        self.bug_mode = bug_mode
        self.control_mode = control_mode # "bot" or "human"
        self.train_mode = train_mode
        self.render_mode = render_mode
        
        self.step_count = 0
        self.MAX_STEPS = 5000

        self.display_screen = pg.display.set_mode((WIDTH, HEIGHT))
        pg.display.set_caption(TITLE)
        self.clock = pg.time.Clock()
        self.running = True
        self.font_name = pg.font.match_font(FONT_NAME)
        self.pause = False

        self.bot_tracked_keys = ['left', 'right', 'jump', 'left_jump', 'right_jump', 'stop']

        self.clear = False
        self.stuck = False
        self.playing = False
        if self.log_mode:
            base_dir = "log"
            os.makedirs(base_dir, exist_ok=True)
            self.logging_name = str(datetime.now()) + ".log"
            logging.basicConfig(
                level=logging.DEBUG,  # 기본 로그 레벨 설정
                format='[%(levelname)s] %(message)s',
                handlers=[
                    logging.FileHandler(os.path.join(base_dir, self.logging_name))       # 파일로도 저장
                    # logging.StreamHandler()                # 콘솔에도 출력
                ]
                )
    def new(self):
        if self.log_mode:
            logging.info('Game start!')
        self.elapsed_time = 0 # running time
        self.time = 0 # 로그 전달 용 time(초 단위)

        self.clear = False
        self.stuck = False
        self.playing = True

        self.step_count = 0 # train시 step 횟수 관리를 위한 변수.

        self.all_sprites = pg.sprite.Group()
        self.platforms = pg.sprite.Group()
        self.spikes = pg.sprite.Group()
        self.spikes_bug = pg.sprite.Group()
        self.bases = pg.sprite.Group()
        self.walls = pg.sprite.Group()
        self.ball = Ball(self, control_mode=self.control_mode, train_mode=self.train_mode)
        self.all_sprites.add(self.ball)
        for plat in PLATFORM_LIST:
            p = Platform(*plat)
            self.platforms.add(p)
            self.all_sprites.add(p)
        for wall in WALL_LIST:
            w = Wall(*wall)
            self.walls.add(w)
            self.all_sprites.add(w)

        if self.bug_mode:
            for spike in SPIKES_NORMAL_LIST:
                s = Spikes(*spike)
                self.spikes.add(s)
                self.all_sprites.add(s)
            for spike_bug in SPIKES_BUG_LIST:
                s = Spikes_bug(*spike_bug)
                self.spikes_bug.add(s)
                self.all_sprites.add(s)            
        else: # there's no bug.
            for spike in SPIKES_LIST:
                s = Spikes(*spike)
                self.spikes.add(s)
                self.all_sprites.add(s)
        for base in BASE_LIST:
            b = Platform_base(*base)
            self.bases.add(b)
            self.all_sprites.add(b)

        self.camera = Camera(WIDTH*6,HEIGHT)
        if not self.train_mode:
            self.run()

    def run(self):
        # Game Loop
        self.playing = True
        self.elapsed_time = 0 # running time
        self.time = 0 # 로그 전달 용 time(초 단위)
        while self.playing:
            self.dt = self.clock.tick(FPS) # self.dt : 진행 시간을 저장하는 변수.
            self.elapsed_time += self.dt 
            self.events()
            self.update()
            self.draw()
            if self.ball.pos.x>2700: #original : 4660
                if self.log_mode:
                    logging.info(f"[{self.elapsed_time * 0.001 + self.time:.3f}초 로그] 특이사항: 게임 클리어, Ball pos: {self.ball.pos}, vel: {self.ball.vel}, key 입력: {self.ball.pressed_keys}")
                self.clear = True
                self.playing = False

        if self.running == False:
            self.quitgame()

        if not self.train_mode & self.playing == False:
            self.show_go_screen()

                # if self.train_mode:
                #     return
                # else:
                #     self.show_go_screen()
 
    def update(self):
        if self.control_mode == "bot" and not self.train_mode: # 즉 bot을 가지고 자동으로 플레이하고 싶을 때,
            obs = np.array(self._get_observation(), dtype=np.float32).reshape(1, -1)
            action, _ = self.model.predict(obs)
            self.ball.pressed_keys = self.bot_tracked_keys[action[0]]
            self.ball.step(action)
        
        elif self.control_mode == "bot" and self.train_mode:
            self.step_count += 1
            if self.step_count >= self.MAX_STEPS:
                self.playing = False
            if self.ball.pos.x>2700:
                self.playing = False

        self.all_sprites.update()

        if self.elapsed_time >= 1000: #시간 따른 로그 출력(장애물 관련 로그 x)
            if self.log_mode:
                logging.info(f"[{self.elapsed_time * 0.001 + self.time:.3f}초 로그] 특이사항: 주기적 로그, Ball pos: {self.ball.pos}, vel: {self.ball.vel}, key 입력: {self.ball.pressed_keys}")
            self.elapsed_time = 0
            self.time += 1

        if self.bug_mode:
            if self.time >= 15:
                self.ball.frozen = True
            if self.time >= 20:
                self.playing = False
                self.running = False

        if self.train_mode & self.time >= 20: # training process간소화를 위해 20초 후 게임 종료.
            self.playing = False

        if self.ball.vel.y > 0:
            hits = pg.sprite.spritecollide(self.ball, self.platforms, False)
            if hits:
                self.ball.pos.y = hits[0].rect.top
                self.ball.vel.y = 0
        #if self.ball.vel.y > 0:
        hits = pg.sprite.spritecollide(self.ball, self.bases, False)
        if hits:
                self.ball.pos.y = hits[0].rect.bottom+40
                self.ball.vel.y = 0
        if self.ball.vel.x > 0:
            hits = pg.sprite.spritecollide(self.ball, self.walls, False)
            if hits:
                self.ball.pos.x = hits[0].rect.left-15
                self.ball.vel.x = 0
        elif self.ball.vel.x < 0:
            hits = pg.sprite.spritecollide(self.ball, self.walls, False)
            if hits:
                self.ball.pos.x = hits[0].rect.right+15
                self.ball.vel.x = 0

        if self.bug_mode:
            #bug spike 정의(아무 변화도 일어나지않도록 설정)
            if pg.sprite.spritecollide(self.ball, self.spikes_bug, False):
                if self.log_mode:
                    logging.info(f"[{self.elapsed_time * 0.001 + self.time:.3f}초 로그] 특이사항: 장애물 충돌, Ball pos: {self.ball.pos}, vel: {self.ball.vel}, key 입력: {self.ball.pressed_keys}")
                self.ball.frozen = True

        hits = pg.sprite.spritecollide(self.ball, self.spikes, False)
        if hits:
            if self.log_mode:
                logging.info(f"[{self.elapsed_time * 0.001 + self.time:.3f}초 로그] 특이사항: 장애물 충돌, Ball pos: {self.ball.pos}, vel: {self.ball.vel}, key 입력: {self.ball.pressed_keys}")
            self.stuck = True
            self.playing = False
            # if self.train_mode:
            #     return
            # else:
            #     self.show_go_screen()

        self.camera.update(self.ball)

    def events(self):
        if self.control_mode == "human":
            for event in pg.event.get():
                if event.type == pg.QUIT:
                    pg.quit()
                    sys.exit()
                if event.type == pg.KEYDOWN:
                    if event.key == pg.K_p:
                        self.pause = True
                        self.pause_game()
                    
                
    def draw(self):
        self.display_screen.fill(BACKGROUND_COLOR)
        for sprite in self.all_sprites:
            self.display_screen.blit(sprite.image, self.camera.apply(sprite))
        pg.display.update()
        
    
    def show_start_screen(self):
        waiting = True
        self.elapsed_time = 0 # running time
        self.time = 0 # 로그 전달 용 time(초 단위)
        while waiting:
            self.display_screen.fill(BACKGROUND_COLOR)
            text = Button(self,TITLE,400,100,0,0,BACKGROUND_COLOR,BACKGROUND_COLOR,90)
            text.create_button()
            play = Button(self,"PLAY",170,200,120,50,GREEN,DARK_GREEN,20,self.new)
            play.create_button()
            instruction = Button(self,'INSTRUCTIONS',320,200,150,50,BRIGHT_ORANGE,ORANGE,20,self.show_instruction)
            instruction.create_button() 
            end = Button(self,"QUIT",500,200,120,50,RED,BRICKRED,20,self.quitgame)
            end.create_button()
            for event in pg.event.get():
                if event.type == pg.QUIT:
                    pg.quit()
                    sys.exit()
            pg.display.update()

    def pause_game(self): 
        while self.pause:    
            for event in pg.event.get():
                if event.type == pg.QUIT:
                    self.quitgame()
            play = Button(self,"RESUME",170,200,120,50,GREEN,DARK_GREEN,20,self.unpause)
            play.create_button()
            end = Button(self,"QUIT",500,200,120,50,RED,BRICKRED,20,self.quitgame)
            end.create_button()
            menu = Button(self,"MENU",340,200,120,50,BRIGHT_ORANGE,ORANGE,20,self.show_start_screen)
            menu.create_button()
            pg.display.update()
            self.clock.tick(60)

    def unpause(self):
        self.pause=False

            
    def show_go_screen(self):
        waiting = True
        self.elapsed_time = 0 # running time
        self.time = 0 # 로그 전달 용 time(초 단위)
        while waiting:
            self.display_screen.fill(BACKGROUND_COLOR)
            if self.clear:
                win = Button(self,"YOU WIN",330,120,0,0,BACKGROUND_COLOR,BACKGROUND_COLOR,100)
                win.create_button()
            elif self.stuck:
                win = Button(self,"YOU LOSE",330,120,0,0,BACKGROUND_COLOR,BACKGROUND_COLOR,100)
                win.create_button()
            restart = Button(self,"RESTART",170,250,120,50,GREEN,DARK_GREEN,20,self.new)
            restart.create_button()
            menu = Button(self,"MENU",320,250,150,50,BRIGHT_ORANGE,ORANGE,20,self.show_start_screen)
            menu.create_button() 
            end = Button(self,"QUIT",500,250,120,50,RED,BRICKRED,20,self.quitgame)
            end.create_button()
            for event in pg.event.get():
                if event.type == pg.QUIT:
                    pg.quit()
            pg.display.update()
            # if time.time() - start_time > 3.0:
            #     waiting = False

    def quitgame(self):
        pg.quit()
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)
        # quit()

    def show_instruction(self):
        waiting = True
        while waiting:
            self.display_screen.fill(BACKGROUND_COLOR)
            back = Button(self,"BACK",30,30,120,50,GREEN,DARK_GREEN,20,self.show_start_screen)
            back.create_button()
            left = Button(self,"Press Left arrow key <- to move left",300,120,0,0,BACKGROUND_COLOR,BACKGROUND_COLOR,40)
            left.create_button()
            right = Button(self,"Press Right arrow key -> to move right",300,200,0,0,BACKGROUND_COLOR,BACKGROUND_COLOR,40)
            right.create_button()
            jump = Button(self,"Press Upper arrow to jump.",300,280,0,0,BACKGROUND_COLOR,BACKGROUND_COLOR,40)
            jump.create_button()
            for event in pg.event.get():
                        if event.type == pg.QUIT:
                            pg.quit()
                            sys.exit()
            pg.display.update()
 
    ### from now: Bot setting

    def reset(self):
        self.new()  # 기존에 있던 초기화 호출
        self.playing = True
        obs = self._get_observation()
        self.update()
        return obs

    def step(self, action): 

        if not self.playing:
            return self._get_observation(), 0.0, True, {}

        # 1. action 전달
        self.ball.step(action)

        # 2. 상태 업데이트
        self.update()

        # 4. 종료 판단
        done = not self.playing
        reward = self._get_reward()
        obs = self._get_observation()

        # 5. step 로그 출력
        # print(f"[Ball.step] called with action: {action}")
        print(f"action: {action} pos: {self.ball.pos}, reward: {reward}")
        # print(f"action: {action}, acc: {self.ball.acc}, vel: {self.ball.vel}, pos: {self.ball.pos}")

        return obs, reward, done, {}

    def _get_observation(self):
        # 정규화 적용
        right_spikes = [x-self.ball.pos.x for x,_ in SPIKES_LIST if self.ball.pos.x <= x]
        if right_spikes:
            distance =  min(right_spikes)
        else:
            distance = 0.0
        
        return [
            self.ball.pos.x / 2760,
            self.ball.pos.y / HEIGHT,
            self.ball.vel.x / 20,
            self.ball.vel.y / 20,
            distance / 800
        ]

    def _get_reward(self):
        # 예시: 오른쪽으로 갈수록 보상 + 장애물에 부딪히면 -10
        reward = 0
        if self.stuck:
            reward += -200
        pos_reward = self.ball.pos.x * 0.09
        time_penalty = self.step_count * 0.1
        if self.clear:
            reward += 100

        return reward + pos_reward - time_penalty

if __name__ == '__main__':
    g = Game()
    g.show_start_screen()
    while g.running:
        g.new()
        g.show_go_screen()
    pg.quit()
