from datetime import datetime


class BearSeasons:
    def __init__(self):
        self.seasons = {
            "winter": [(11, 15), (3, 31)],
            "spring": [(4, 1), (6, 14)],
            "summer": [(6, 15), (8, 31)],
            "autumn": [(9, 1), (11, 14)],
        }

    def get_season(self, date):
        month = date.month
        day = date.day

        if (month == 11 and day >= 15) or month == 12 or month == 1 or month == 2 or (month == 3 and day <= 31):
            return "winter"
        elif (month == 4 and day >= 1) or month == 5 or (month == 6 and day <= 14):
            return "spring"
        elif (month == 6 and day >= 15) or month == 7 or month == 8:
            return "summer"
        elif (month == 9 and day >= 1) or month == 10 or (month == 11 and day <= 14):
            return "autumn"
        else:
            return ""