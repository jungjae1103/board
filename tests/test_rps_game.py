import unittest

from utils.rps_game import determine_rps_winner


class DetermineRPSWinnerTests(unittest.TestCase):
    def test_all_same_is_tie(self):
        result = determine_rps_winner(
            {"player1": "rock", "player2": "rock", "player3": "rock", "player4": "rock"}
        )
        self.assertTrue(result["is_tie"])
        self.assertEqual(result["losers"], [])

    def test_three_types_is_tie(self):
        result = determine_rps_winner(
            {"player1": "rock", "player2": "paper", "player3": "scissors", "player4": "rock"}
        )
        self.assertTrue(result["is_tie"])

    def test_two_vs_two_winning_hand_wins(self):
        result = determine_rps_winner(
            {"player1": "rock", "player2": "paper", "player3": "rock", "player4": "paper"}
        )
        self.assertFalse(result["is_tie"])
        self.assertEqual(result["winners"], ["player2", "player4"])
        self.assertEqual(result["losers"], ["player1", "player3"])

    def test_three_vs_one_eliminates_loser(self):
        result = determine_rps_winner(
            {"player1": "scissors", "player2": "scissors", "player3": "scissors", "player4": "paper"}
        )
        self.assertFalse(result["is_tie"])
        self.assertEqual(result["winners"], ["player1", "player2", "player3"])
        self.assertEqual(result["losers"], ["player4"])

    def test_one_vs_three_eliminates_losers(self):
        result = determine_rps_winner(
            {"player1": "rock", "player2": "scissors", "player3": "scissors", "player4": "scissors"}
        )
        self.assertFalse(result["is_tie"])
        self.assertEqual(result["winners"], ["player1"])
        self.assertEqual(result["losers"], ["player2", "player3", "player4"])


if __name__ == "__main__":
    unittest.main()
