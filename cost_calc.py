import copy

input_string = "10--1000,500,0-5000,100,5"


def get_cost(input_string, hours):
    output = 0
    input_string = input_string.split("--")
    output += int(input_string[0])
    tuples = []
    for s in input_string[1].split("-"):
        tuples.append(tuple(map(int, s.split(","))))

    prev_hourly_point = 0
    for idx, t in enumerate(tuples):
        old_hrs = hours
        fixed, timpris, hourly_point = t
        if hours >= hourly_point:
            output += fixed
            if idx + 1 < len(tuples):
                if hours >= tuples[idx + 1][2]:
                    old_hrs = copy.deepcopy(hours)
                    hours = tuples[idx + 1][2] - 1
            output += timpris * (hours - ((hourly_point - 1) if hourly_point > 0 else 0))

            hours = old_hrs
        else:
            break

    print(input_string)

    return input_string


get_cost(input_string, 5)
