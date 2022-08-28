from flask import Flask, render_template

app = Flask(__name__)


@app.route("/form")
def test():
    return render_template("form.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0")
