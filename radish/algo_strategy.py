import gamelib
import random
import math
import warnings
from sys import maxsize
import json

"""
Most of the algo code you write will be in this file unless you create new
modules yourself. Start by modifying the 'on_turn' function.

Advanced strategy tips: 

  - You can analyze action frames by modifying on_action_frame function

  - The GameState.map object can be manually manipulated to create hypothetical 
  board states. Though, we recommended making a copy of the map to preserve 
  the actual current map state.
"""


class AlgoStrategy(gamelib.AlgoCore):
    def __init__(self):
        super().__init__()
        seed = random.randrange(maxsize)
        random.seed(seed)
        gamelib.debug_write('Random seed: {}'.format(seed))

    def on_game_start(self, config):
        """ 
        Read in config and perform any initial setup here 
        """
        gamelib.debug_write('Configuring your custom algo strategy...')
        self.config = config
        global FILTER, ENCRYPTOR, DESTRUCTOR, PING, EMP, SCRAMBLER, BITS, CORES
        FILTER = config["unitInformation"][0]["shorthand"]
        ENCRYPTOR = config["unitInformation"][1]["shorthand"]
        DESTRUCTOR = config["unitInformation"][2]["shorthand"]
        PING = config["unitInformation"][3]["shorthand"]
        EMP = config["unitInformation"][4]["shorthand"]
        SCRAMBLER = config["unitInformation"][5]["shorthand"]
        BITS = 1
        CORES = 0
        # This is a good place to do initial setup
        self.scored_on_locations = []
        self.got_damage = True
        self.RUSH = True
        self.RUSH_ATTEMPTED = False

    def on_turn(self, turn_state):
        """
        This function is called every turn with the game state wrapper as
        an argument. The wrapper stores the state of the arena and has methods
        for querying its state, allocating your current resources as planned
        unit deployments, and transmitting your intended deployments to the
        game engine.
        """
        game_state = gamelib.GameState(self.config, turn_state)
        gamelib.debug_write('Performing turn {} of your custom algo strategy'.format(game_state.turn_number))
        game_state.suppress_warnings(True)  # Comment or remove this line to enable warnings.

        self.starter_strategy(game_state)

        game_state.submit_turn()

    """
    NOTE: All the methods after this point are part of the sample starter-algo
    strategy and can safely be replaced for your custom algo.
    """

    def starter_strategy(self, game_state):

        # First, place basic defenses
        self.build_defences(game_state)
        got_damage = True
        bit_increment = (game_state.turn_number // 10) + 5
        if game_state.turn_number == 1 or game_state.turn_number > 10:
            game_state.attempt_spawn(SCRAMBLER, [6, 7], 1)
            game_state.attempt_spawn(SCRAMBLER, [21, 7], 1)
        if game_state.get_resource(BITS) > bit_increment * 2:
            # To simplify we will just check sending them from back left and right
            ping_spawn_location_options = [[11, 2], [16, 2]]
            best_location = self.least_damage_spawn_location(game_state, ping_spawn_location_options)
            game_state.attempt_spawn(PING, best_location, 1000)
            self.RUSH_ATTEMPTED = True

    def filter_blocked_locations(self, locations, game_state):
        filtered = []
        for location in locations:
            if not game_state.contains_stationary_unit(location):
                filtered.append(location)
        return filtered

    def build_defences(self, game_state):
        """
        Build basic defenses using hardcoded locations.
        Remember to defend corners and avoid placing units in the front where enemy EMPs can attack them.
        """
        # Useful tool for setting up your base locations: https://www.kevinbai.design/terminal-map-maker
        # More community tools available at: https://terminal.c1games.com/rules#Download
        basic_filter_locations = [[5, 11], [6, 11], [21, 11], [22, 11], [6, 9], [21, 9], [7, 8], [20, 8], [8, 7],
                                  [19, 7], [9, 6], [18, 6], [10, 5], [12, 5], [13, 5], [14, 5], [15, 5], [17, 5],
                                  [11, 4], [16, 4], [3, 11], [2, 12], [1, 13], [24, 11], [25, 12], [26, 13]]
        basic_destructor_locations = [[5, 10], [22, 10]]
        game_state.attempt_spawn(DESTRUCTOR, basic_destructor_locations)
        game_state.attempt_spawn(FILTER, basic_filter_locations)

        encryptor_locations = [[13, 3], [14, 3], [13, 2], [14, 2], [13, 1], [14, 1], [13, 0], [14, 0], [12, 1], [15, 1],
                               [12, 2], [15, 2]]
        game_state.attempt_spawn(ENCRYPTOR, encryptor_locations[0])

        secondary_destructor_locations = [[27, 13], [0, 13], [21, 10], [6, 10], [26, 12], [25, 11], [1, 12], [24, 10],
                                          [2, 11], [3, 10], [20, 10], [20, 9]]
        game_state.attempt_spawn(DESTRUCTOR, secondary_destructor_locations[0:7])

        # TODO on rush turns, make sure at least one encryptor
        if game_state.get_resource(CORES) >= 8:
            if game_state.turn_number < 10:
                game_state.attempt_spawn(ENCRYPTOR, encryptor_locations[0:7])
            else:
                game_state.attempt_spawn(ENCRYPTOR, encryptor_locations)

        game_state.attempt_spawn(DESTRUCTOR, secondary_destructor_locations)
        game_state.attempt_upgrade(
            [[5, 11], [6, 11], [21, 11], [22, 11], [6, 9], [21, 9], [3, 11], [2, 12], [1, 13], [24, 11], [25, 12],
             [26, 13]])
        game_state.attempt_upgrade(secondary_destructor_locations)
        game_state.attempt_upgrade(basic_destructor_locations)
        if game_state.get_resource(CORES) >= 8:
            game_state.attempt_upgrade(encryptor_locations)
        # upgrade filters so they soak more damage

    def least_damage_spawn_location(self, game_state, location_options):
        """
        This function will help us guess which location is the safest to spawn moving units from.
        It gets the path the unit will take then checks locations on that path to 
        estimate the path's damage risk.
        """
        damages = []
        # Get the damage estimate each path will take
        for location in location_options:
            path = game_state.find_path_to_edge(location)
            damage = 0
            for path_location in path:
                # Get number of enemy destructors that can attack the final location and multiply by destructor damage
                damage += len(game_state.get_attackers(path_location, 0)) * gamelib.GameUnit(DESTRUCTOR,
                                                                                             game_state.config).damage_i
            damages.append(damage)

        # Now just return the location that takes the least damage
        return location_options[damages.index(min(damages))]

    def detect_enemy_unit(self, game_state, unit_type=None, valid_x=None, valid_y=None):
        total_units = 0
        for location in game_state.game_map:
            if game_state.contains_stationary_unit(location):
                for unit in game_state.game_map[location]:
                    if unit.player_index == 1 and (unit_type is None or unit.unit_type == unit_type) and (
                            valid_x is None or location[0] in valid_x) and (valid_y is None or location[1] in valid_y):
                        total_units += 1
        return total_units

    def on_action_frame(self, turn_string):
        """
        This is the action frame of the game. This function could be called 
        hundreds of times per turn and could slow the algo down so avoid putting slow code here.
        Processing the action frames is complicated so we only suggest it if you have time and experience.
        Full doc on format of a game frame at: https://docs.c1games.com/json-docs.html
        """
        # Let's record at what position we get scored on
        state = json.loads(turn_string)
        events = state["events"]
        breaches = events["breach"]
        self.got_damage = False;
        for breach in breaches:
            location = breach[0]
            unit_owner_self = True if breach[4] == 1 else False
            if unit_owner_self:
                self.got_damage = True;
            # When parsing the frame data directly, 
            # 1 is integer for yourself, 2 is opponent (StarterKit code uses 0, 1 as player_index instead)
            if not unit_owner_self:
                gamelib.debug_write("Got scored on at: {}".format(location))
                self.scored_on_locations.append(location)
                gamelib.debug_write("All locations: {}".format(self.scored_on_locations))
        if self.RUSH_ATTEMPTED and not self.got_damage:
            self.RUSH = False;


if __name__ == "__main__":
    algo = AlgoStrategy()
    algo.start()
