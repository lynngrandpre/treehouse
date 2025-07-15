import pygame
import random


CANVAS_WIDTH     = 800   # Width  of canvas   
CANVAS_HEIGHT    = 400   # Height of canvas
BALL_SIZE        = 25    # ball to play with
BUTTON_SIZE      = 75    # diameter of the buttons 
GOAL             = 50     # number of correct guesses to end game
DONE             = 5     # number of incorrect guesses to end the game
DELAY            = 0.0001 # for my bouncing ball at the end
INITIAL_VELOCITY = 5     # for the ball
PADDLE_WIDTH     = 50    # of course we need a paddle
PADDLE_HEIGHT    = 15    # and a paddle needs some thickness
PADDLE_VELOCITY  = 5     # How fast the paddle moves


def main():
    # This program will create a state capital
    # quiz game to help kids learn the state capitals.
    # If a state has an NBA team and the player can
    # name it, they get to play a 3-point shooting game
    # to earn bonus points
    # lets use pictures of the states and buttons to select 
    # capitals


   

    # set up a dictionary of the state images with 
    # the state name as the key

    state_info = {
    'California': {
        'capital': 'Sacramento',
        'image': 'california.png',
        'nba_teams': ['Los Angeles Lakers', 'Los Angeles Clippers', 'Golden State Warriors', 'Sacramento Kings']
    },
    'Texas': {
        'capital': 'Austin',
        'image': 'texas.png',
        'nba_teams': ['Houston Rockets', 'Dallas Mavericks', 'San Antonio Spurs']
    },
    'Alaska': {
        'capital': 'Juneau',
        'image': 'alaska.png',
        'nba_teams': []  # No NBA teams here
    },
    'Rhode Island': {
        'capital': 'Providence',
        'image': 'rhode_island.png',
        'nba_teams': []  # No NBA teams here
    },
    'Massachusetts': {
        'capital': 'Boston',
        'image': 'massachusetts.png',
        'nba_teams': ['Boston Celtics']  
    },
    'Connecticut': {
        'capital': 'Hartford',
        'image': 'connecticut.png',
        'nba_teams': []  # No NBA teams here
    },
    'Maine': {
        'capital': 'Augusta',
        'image': 'maine.png',
        'nba_teams': []  # No NBA teams here
    },
    'Vermont': {
        'capital': 'Montpelier',
        'image': 'vermont.png',
        'nba_teams': []  # No NBA teams here
    },
    'New Hampshire': {
        'capital': 'Concord',
        'image': 'new_hampshire.png',
        'nba_teams': []  # No NBA teams here
    },
    'Alabama': {
        'capital': 'Montgomery',
        'image': 'alabama.png',
        'nba_teams': []  # No NBA teams here
    },
    'Arkansas': {
        'capital': 'Little Rock',
        'image': 'arkansas.png',
        'nba_teams': []  # No NBA teams here
    },
    'Colorado': {
        'capital': 'Denver',
        'image': 'colorado.png',
        'nba_teams': ['Denver Nuggets']  
    },
    'Delaware': {
        'capital': 'Dover',
        'image': 'delaware.png',
        'nba_teams': []  # No NBA teams here
    },
    'Florida': {
        'capital': 'Tallahassee',
        'image': 'florida.png',
        'nba_teams': ['Miami Heat', 'Orlando Magic']  
    },
    'Georgia': {
        'capital': 'Atlanta',
        'image': 'georgia.png',
        'nba_teams': ['Atlanta Hawks']  
    },
    'Hawaii': {
        'capital': 'Honalulu',
        'image': 'hawaii.png',
        'nba_teams': []  # No NBA teams here
    },
    'Idaho': {
        'capital': 'Boise',
        'image': 'idaho.png',
        'nba_teams': []  # No NBA teams here
    },
    'Illinois': {
        'capital': 'Springfield',
        'image': 'illinois.png',
        'nba_teams': ['Chicago Bulls']  
    },
    'Indiana': {
        'capital': 'Indianapolis',
        'image': 'indiana.png',
        'nba_teams': ['Indiana Pacers']  
    },   
    'Iowa': {
        'capital': 'Des Moines',
        'image': 'iowa.png',
        'nba_teams': []  # No NBA teams here
    },
    'Kansas': {
        'capital': 'Topeka',
        'image': 'kansas.png',
        'nba_teams': []  # No NBA teams here
    },
    'Kentucky': {
        'capital': 'Frankfort',
        'image': 'kentucky.png',
        'nba_teams': []  # No NBA teams here
    },
    'Louisiana': {
        'capital': 'Baton Rouge',
        'image': 'louisiana.png',
        'nba_teams': ['New Orleans Pelicans']  
    },
    'Maryland': {
        'capital': 'Annapolis',
        'image': 'maryland.png',
        'nba_teams': []  # No NBA teams here
    },
    'Michigan': {
        'capital': 'Lansing',
        'image': 'michigan.png',
        'nba_teams': ['Detroit Pistons']  
    },
    'Minnesota': {
        'capital': 'Saint Paul',
        'image': 'minnesota.png',
        'nba_teams': ['Minnesota Timberwolves']  
    },
    'Mississippi': {
        'capital': 'Jackson',
        'image': 'mississippi.png',
        'nba_teams': []  # No NBA teams here
    },
    'Missouri': {
        'capital': 'Jefferson City',
        'image': 'missouri.png',
        'nba_teams': []  # No NBA teams here
    },
    'Montana': {
        'capital': 'Helena',
        'image': 'montana.png',
        'nba_teams': [] # No NBA teans here
    },
    'Nebraska': {
        'capital': 'Lincoln',
        'image': 'nebraska.png',
        'nba_teams': []  # No NBA teams here
    },
    'Nevada': {
        'capital': 'Carson City',
        'image': 'nevada.png',
        'nba_teams': []  # No NBA teams here
    },
    'New Jersey': {
        'capital': 'Trenton',
        'image': 'new_jersey.png',
        'nba_teams': []  # No NBA teams here
    },
    'New Mexico': {
        'capital': 'Santa Fe',
        'image': 'new_mexico.png',
        'nba_teams': []  # No NBA teams here
    },
    'New York': {
        'capital': 'Albany',
        'image': 'new_york.png',
        'nba_teams': ['Brooklyn Nets', 'New York Knicks']  
    },
    'North Carolina': {
        'capital': 'Raliegh',
        'image': 'north_carolina.png',
        'nba_teams': ['Charlotte Hornets']  
    },
    'North Dakota': {
        'capital': 'Bismarck',
        'image': 'north_dakotaa.png',
        'nba_teams': []  # No NBA teams here
    },
    'Ohio': {
        'capital': 'Columbus',
        'image': 'ohio.png',
        'nba_teams': ['Cleveland Cavaliers']  
    },
    'Oklahoma': {
        'capital': 'Oklahoma City',
        'image': 'oklahoma.png',
        'nba_teams': ['Oklahoma City Thunder']  
    },
    'Oregon': {
        'capital': 'Salem',
        'image': 'oregon.png',
        'nba_teams': ['Portland Trail Blazers'] 
    },
    'Pennsylvania': {
        'capital': 'Harrisburg',
        'image': 'pennsylvania.png',
        'nba_teams': ['Philadelphia 76ers']  
    },
    'South Carolina': {
        'capital': 'Columbia',
        'image': 'alaska.png',
        'nba_teams': []  # No NBA teams here
    },
    'South Dakota': {
        'capital': 'Pierre',
        'image': 'south_dakota.png',
        'nba_teams': []  # No NBA teams here
    },
    'Tennessee': {
        'capital': 'Nashville',
        'image': 'tennessee.png',
        'nba_teams': ['Memphis Grizzlies']  
    },
    'Utah': {
        'capital': 'Salt Lake City',
        'image': 'utah.png',
        'nba_teams': ['Utah Jazz']  
    },
    'Virginia': {
        'capital': 'Richmond',
        'image': 'virginia.png',
        'nba_teams': []  # No NBA teams here
    },
    'Washington': {
        'capital': 'Olympia',
        'image': 'washington.png',
        'nba_teams': []  # No NBA teams here
    },
    'West Virginia': {
        'capital': 'Charleston',
        'image': 'west_virginia.png',
        'nba_teams': []  # No NBA teams here
    },
    'Wyoming': {
        'capital': 'Cheyenne',
        'image': 'wyoming.png',
        'nba_teams': []  # No NBA teams here
    },
    'Wisconsin': {
        'capital': 'Madison',
        'image': 'wisconsin.png',
        'nba_teams': ['Milwaukee Bucks']  
    },
    'Arizona': {
        'capital': 'Phoenix',
        'image': 'arizona.png',
        'nba_teams': ['Phoenix Suns']  
    }
    
    } # end of state_info


    canvas = Canvas(CANVAS_WIDTH, CANVAS_HEIGHT)
    

    # let's initilize our variables
    wrong_answers = []          # keep track of the states you get wrong in a list
    state_list    = []          # initialize a list for all the states
    used_list     = []          # to store a list of states that were corrrectly guessed
    capital_list  = []          # list of all the capitals 
    rnd_cap       = []          # list of 4 random capitals to use on buttons
    ball_color    = ['black', 'red', 'orange', 'yellow','green', 'blue', 'purple']

    num_correct   = 0           # count how many we get right  
    num_wrong     = 0           # count how many we get wrong  
    num_states    = 0           # count how many states we have gone through
    what_round    = 1           # We'll do a few states at a time... in rounds
    guess         = ''          # stores the user's guess after a button is clicked
    message2      = ''          # available place for sending another message 

    # initialize boolean variables to track whick button was clicked
    # these 5 variable become True when the corrsponding button is clicked
    b_1 = False                 
    b_2 = False                 
    b_3 = False 
    b_4 = False
    b_5 = False
    game_over = False           # change to True to end the game

    # Let's draw some buttons on the canvas
    # Buttons will all be in a row near the bottom of the canvas
    
    button_1 = draw_button(canvas, BUTTON_SIZE, CANVAS_WIDTH/6, 'red')
    button_2 = draw_button(canvas, BUTTON_SIZE, CANVAS_WIDTH * 2/6, 'green')
    button_3 = draw_button(canvas, BUTTON_SIZE, CANVAS_WIDTH*3/6, 'blue')
    button_4 = draw_button(canvas, BUTTON_SIZE, CANVAS_WIDTH * 4/6, 'yellow')
    button_5 = draw_button(canvas, BUTTON_SIZE, CANVAS_WIDTH*5/6, 'black')
   
    # we'll use the leftmost x location later
    # when we figure out which button was "pushed"

    button_1_left_x = canvas.get_left_x(button_1)
    button_2_left_x = canvas.get_left_x(button_2)
    button_3_left_x = canvas.get_left_x(button_3)
    button_4_left_x = canvas.get_left_x(button_4)
    button_5_left_x = canvas.get_left_x(button_5)
    # and put them in a list for easy access later
    button_loc_list = [button_1_left_x ,
        button_2_left_x,
        button_3_left_x,
        button_4_left_x,
        button_5_left_x ]

    # and let's make a scoreboard to keep track of how many you got right
    scoreboard = canvas.create_rectangle(
        CANVAS_WIDTH - 170,
        20,
        CANVAS_WIDTH - 25,
        CANVAS_HEIGHT/3,
        'yellow',
        'black' 
    )
    # add the word SCORE
    canvas.create_text(
        canvas.get_left_x(scoreboard) + 20,
        canvas.get_top_y(scoreboard)+ 5,
        'SCORE', 
        font_size = 25)

    # add the word CORRECT
    canvas.create_text(
        canvas.get_left_x(scoreboard) + 5,
        canvas.get_top_y(scoreboard)+ 35,
        'Correct', 
        font_size = 18)   

    # add the word WRONG
    canvas.create_text(
        canvas.get_left_x(scoreboard) + 75,
        canvas.get_top_y(scoreboard)+ 35,
        'Wrong', 
        font_size = 18)    

    # Add the number of questions answered correctly
    score = canvas.create_text(
        canvas.get_left_x(scoreboard) + 5,
        canvas.get_top_y(scoreboard)+ 70,
        str(num_correct), 
        font_size = 50)

    # Add the number of questions answered incorrectly
    num_wrong_score = canvas.create_text(
        canvas.get_left_x(scoreboard) + 80,
        canvas.get_top_y(scoreboard)+ 70,
        str(num_wrong), 
        font_size = 50)


    # let's make a list of all the states in our state_info dictionary
    # and another list of all the capitals in the state_info dictionary 
    # Loop over each state in the dictionary
    for state, info in state_info.items():
        # Get the capital of the state
        capital = info['capital']
        # Add the capital to our list
        capital_list.append(capital)
        # get the state name and add it to the state list
        state_list.append(state)
    
    
    # we'll take states off the list as they are guessed correctly
    # capital list will remain intact so we can pick from it to label buttons

    # Let's put up a welcome message -
    # this is where the state names will appear
    message1 = "Welcome to my game"
    txt_state_name = canvas.create_text(
        CANVAS_WIDTH/6,
        CANVAS_HEIGHT /3,
        message1, 
        font_size = 25)
    time.sleep(1)       # keep message up for 1 second
    
    # erase the weelcome message
    canvas.change_text(txt_state_name, '')
 
    # create another text box area for message 2
    txt_message2 = canvas.create_text(
        CANVAS_WIDTH/6,
        CANVAS_HEIGHT /3 +50,
        message2, 
        font_size = 25,
        color = 'red')
    

    while not game_over:     
        # pick a random state from the state_list
        #If we've run out of states, end the game
        if state_list:
            key = random.choice(list(state_list))
        else:
            game_over = True

        # we'll need four random capitals to choose from
        # plus the correct capital
        correct_capital = state_info[key]['capital']
        
        # now pick 4 random capitals from capital_list
        rnd_cap = []       # start with an empty list then pick 4
        while len(rnd_cap) < 4:
            new_item = random.choice(capital_list)
            while new_item == correct_capital:        # make sure we didn't pick the correct one
               new_item = random.choice(capital_list) # try again
            
            # Check if the new item is already in the list
            # so we don't get repeat items
            if new_item not in rnd_cap:
                rnd_cap.append(new_item)
           
        # we want to add the correct_capital to my random captial list in a random order
        # Generate a random index between 0 and the length of the list
        random_index = random.randint(0, len(rnd_cap))
        # Insert the new item at the random index
        rnd_cap.insert(random_index, correct_capital)
        
        
        # and we'll write the state name on the canvas
        # EVENTUALLY we can change to an option for state image or name or both
        canvas.change_text(txt_state_name, key)
        show_state_image(canvas, key, state_info)
        # let's put names of state capitals under the buttons
        # first erase them, then write them
        erase_button_labels(canvas)
        for i in range(5):
            txt_capital_name = canvas.create_text(
                button_loc_list[i],
                CANVAS_HEIGHT - 40,
                rnd_cap[i], 
                font_size = 15)

        canvas.wait_for_click()             # wait for user to select a button
        x_click = canvas.get_mouse_x()
        y_click = canvas.get_mouse_y()
        # Let's figure out which button was pressed
        if x_click > button_1_left_x and x_click < BUTTON_SIZE + button_1_left_x:
            guess = rnd_cap[0]
            b_1 = True
        if x_click > button_2_left_x and x_click < BUTTON_SIZE + button_2_left_x:
            guess = rnd_cap[1]
            b_2 = True
        if x_click > button_3_left_x and x_click < BUTTON_SIZE + button_3_left_x:
            guess = rnd_cap[2]
            b_3 = True
        if x_click > button_4_left_x and x_click < BUTTON_SIZE + button_4_left_x:
            guess = rnd_cap[3]
            b_4 = True
        if x_click > button_5_left_x and x_click < BUTTON_SIZE + button_5_left_x:
            guess = rnd_cap[4]
            b_5 = True
        num_states += 1
       

        if guess == state_info[key]['capital']:
            num_correct +=1 # increment the score
            # you got it right let's remove it from the list
            safe_remove(key, state_list)
                
        else:
            num_wrong += 1
            wrong_answers.append(key)  
            
        # update the scoreboard
        canvas.change_text(score, str(num_correct))
        canvas.change_text(num_wrong_score, str(num_wrong))
        
        if num_correct == GOAL:
            game_over = True
        
        if num_wrong == DONE:
            game_over = True
        
    # Game is over... send the user some messages

    canvas.change_text(txt_state_name, 'GAME OVER')
    if num_wrong >=1:
        canvas.change_text(txt_message2,'You missed these states:' )
        time.sleep(.5)
        list_string = ', '.join(wrong_answers)
        canvas.change_text(txt_message2, list_string)
    else:
        message2 = 'congratulations! You got them all right!'
        canvas.change_text(txt_message2, message2   )

    
    erase_button_labels(canvas)             # erase the button labels
    time.sleep(2)                           # wait 2 seconds
    canvas.change_text(txt_message2, '')    # Erase message 2 text area
    canvas.change_text(txt_state_name, '')  # Erase state name text area
    time.sleep(1)
    stack_balls(canvas, button_1, button_2, button_3, button_4, button_5)    
    canvas.delete(button_1)
    canvas.delete(button_2)
    canvas.delete(button_3)
    canvas.delete(button_4)
    small_ball = shrink_it(canvas, button_5)

    # now we have one small black ball....
    # and it will be lonely so let's make some more balls
    # and play a paddle game called ping

    

    for i in range(7):
        x_speed = INITIAL_VELOCITY +(i * -5 )
        ping(canvas, small_ball, ball_color[i],x_speed)


    canvas.delete(small_ball)       # delete my small ball
    canvas.change_text(txt_message2, 'Thanks for Playing')



def ping(canvas, obj, col, x_vel):
    # a little paddle game to play
    # maybe in the next version!! 
    # for now just shoot some balls out
    
    ball_x = canvas.get_left_x(obj)
    ball_y = canvas.get_top_y(obj)
    
    x_velocity = x_vel
    y_velocity = INITIAL_VELOCITY
    ball = canvas.create_oval(ball_x, ball_y,
                            ball_x + BALL_SIZE,
                            ball_y + BALL_SIZE,
                            col, 'black')       # black outline, colored ball
    
    
     

    # let's draw a full length vertical line along the left side of the scoreboard
    # first we locate the scoreboard...
    sb_x = CANVAS_WIDTH - 170
    right_side = canvas.create_line(sb_x, 0,sb_x, CANVAS_HEIGHT)
   
    #It would be nice to have 2 buttons to control the paddle direction
    #but_left = create_button(canvas, BUTTON_SIZE, sb_x + 2* BALL_SIZE + 10, CANVAS_HEIGHT/2,'blue')
    #but_right = create_button(canvas, BUTTON_SIZE, sb_x + 2* BALL_SIZE + 10, CANVAS_HEIGHT* 3/4,'black')
    #txt_but_left = canvas.create_text(sb_x + 2* BALL_SIZE - 10 ,  
    #                                    CANVAS_HEIGHT/2,
    #                                     'LEFT' , 
    #                                    font_size = 18,
    #                                     color = 'yellow' )
    #txt_but_right = canvas.create_text(sb_x + 2* BALL_SIZE - 15 ,  
    #                                    CANVAS_HEIGHT*3/4 - 10,
    #                                     'RIGHT' , 
    #                                     font_size = 18,
    #                                     color = 'yellow' )
    ###but_left_x  = canvas.get_left_x(but_left)
    ###but_right_x = canvas.get_left_x(but_right)
    # and let's play until the ball goes off the bottom of the canvas
    while ball_y < CANVAS_HEIGHT:
        ball_x += x_velocity
        ball_y += y_velocity
        canvas.moveto(ball, ball_x, ball_y)
        time.sleep(DELAY)
        if ball_x < BALL_SIZE/2:
            x_velocity = - x_velocity  
        if ball_x > sb_x - BALL_SIZE/2 :
            x_velocity = - x_velocity
        if ball_y < BALL_SIZE / 2 :
            y_velocity = - y_velocity
        
   
   

def create_paddle(canvas, top_l_x):
    # let's make a paddle that will slide along the bottom of the canvas
    # x and y coordinates of the top left corner of the paddle
    left_x   = top_l_x
    top_y    = CANVAS_HEIGHT - PADDLE_HEIGHT
    right_x  = PADDLE_WIDTH + CANVAS_WIDTH/2
    bottom_y = CANVAS_HEIGHT
    
    return canvas.create_rectangle(
            left_x, 
            top_y, 
            right_x, 
            bottom_y,
            'black'
    )



def safe_remove(key, state_list):
    # function checks to make sure there is an item in the list to be removed
    if state_list:          
        state_list.remove(key)


def shrink_it(canvas, ball):
    # this function takes an oval object and shrinks it
    x = canvas.get_left_x(ball)
    y = canvas.get_top_y(ball)

    for i in range(3,0,-1):
        canvas.delete(ball)     # delete the ball
        ball = canvas.create_oval(x, y, x + i*BALL_SIZE, y + i*BALL_SIZE)    # and create a new, slightly smaller one
        time.sleep(.5)          # so we can watch it shrink
    return ball # return the small ball 

def stack_balls( canvas, ball_1, ball_2, ball_3, ball_4, ball_5):
    # This function moves all the buttons on top of on another
    canvas.moveto(ball_1,CANVAS_WIDTH/2, CANVAS_HEIGHT/3) 
    time.sleep(1) 
    canvas.moveto(ball_2,CANVAS_WIDTH/2, CANVAS_HEIGHT/3) 
    time.sleep(1)    
    canvas.moveto(ball_3,CANVAS_WIDTH/2, CANVAS_HEIGHT/3)       
    time.sleep(1) 
    canvas.moveto(ball_4,CANVAS_WIDTH/2, CANVAS_HEIGHT/3) 
    time.sleep(1)
    canvas.moveto(ball_5, CANVAS_WIDTH/2, CANVAS_HEIGHT/3)  



def erase_button_labels(canvas):
    canvas.create_rectangle(0,CANVAS_HEIGHT-45, CANVAS_WIDTH,CANVAS_HEIGHT,'white')

def draw_button(canvas, size, x_center, color):
    # draws a button at the bottom of the canvas
    y_center = CANVAS_HEIGHT - 1.5* BUTTON_SIZE
    return canvas.create_oval(
        x_center - BUTTON_SIZE/2, 
        y_center - BUTTON_SIZE / 2, 
        x_center + BUTTON_SIZE/2, 
        y_center + BUTTON_SIZE/2, 
        color,'black')

def create_button(canvas, size, x, y, color):
    # draws a button centered at x, y
    y_center = y
    x_center = x
    return canvas.create_oval(
        x_center - BUTTON_SIZE/2, 
        y_center - BUTTON_SIZE / 2, 
        x_center + BUTTON_SIZE/2, 
        y_center + BUTTON_SIZE/2, 
        color,'black')

def show_state_image(canvas, state_name, state_info):
    image_file = state_info[state_name]['image']
    '''
    # ADD THIS LATER
    if image_file:
        #canvas.create_image(200, 200, image_file)  # Adjust coordinates as needed
        print(f"The image for {state_name} is {image_file}")
    '''


if __name__ == '__main__':
    main()