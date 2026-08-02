The logic here is almost the same in GPT-2, GPT-3, Llama, Mistral, etc. The models are much more complex, but the **generation loop** is fundamentally the same.

We'll understand it from **first principles**.

---

# First, what is the purpose of `generate()`?

The `forward()` method answers:

> **"Given some input, what should the next token probably be?"**

The `generate()` method answers:

> **"Keep asking that question repeatedly until we've generated an entire sentence."**

Think of it like talking to someone.

You say:

```text
Once upon a
```

The model predicts

```text
time
```

Now the sentence becomes

```text
Once upon a time
```

Now it predicts

```text
there
```

Sentence becomes

```text
Once upon a time there
```

Then

```text
was
```

Then

```text
a
```

Then

```text
king
```

The model is simply doing this over and over.

---

# The complete generation pipeline

Before looking at the code, understand this loop.

```text
Current sentence
        │
        ▼
Run the model
        │
        ▼
Predict next token
        │
        ▼
Choose one token
        │
        ▼
Append it
        │
        ▼
Repeat
```

That's literally the entire generation process.

---

# Method definition

```python
def generate(self, idx, max_new_tokens):
```

Let's understand the parameters.

## What is `idx`?

This is the **starting text**.

Suppose we already have

```text
I love
```

Tokenized

```text
I      love

↓

10     35
```

Then

```python
idx =
[[10,35]]
```

Notice the shape.

```text
(B,T)

1 × 2
```

because

* one sentence
* two tokens

---

## What is `max_new_tokens`?

Suppose

```python
max_new_tokens = 5
```

The model will generate

```text
Token 1
Token 2
Token 3
Token 4
Token 5
```

Then stop.

---

# The loop

```python
for _ in range(max_new_tokens):
```

This is simply

```python
for i in range(5):
```

except the variable isn't used.

Python programmers often write

```python
_
```

to mean

> "I don't care about this variable."

---

Imagine

```python
max_new_tokens = 3
```

The loop becomes

Iteration 1

↓

Generate one token

Iteration 2

↓

Generate one token

Iteration 3

↓

Generate one token

Done.

---

# Step 1

```python
logits, loss = self(idx)
```

This line is extremely important.

Remember

```python
self(...)
```

calls

```python
forward(...)
```

So this is actually

```python
logits, loss = self.forward(idx)
```

We're asking the model

> "Given these tokens, what do you think comes next?"

---

Suppose

Current sentence

```text
I love
```

The model returns

```text
Predictions for I

Predictions for love
```

Notice something.

It predicts for **every token**.

Why?

Because during training every token learns to predict its next token.

---

Suppose

```python
idx =
[[10,35]]
```

Shape

```text
(1,2)
```

After the model

```python
logits.shape
```

becomes

```text
(1,2,65)
```

Let's understand this.

---

The model predicted

For token

```text
I
```

↓

65 scores

For token

```text
love
```

↓

65 scores

So

```text
1 sentence

2 positions

65 predictions each
```

Hence

```text
(1,2,65)
```

---

# Visualizing logits

Imagine

Vocabulary

```text
0 = I

1 = love

2 = Python

3 = cats
```

Model output

```text
[
  [
      [2,5,1,8],   ← predictions after "I"

      [1,9,3,2]    ← predictions after "love"
  ]
]
```

There are predictions for every position.

---

# But we only want ONE prediction

Why?

Because we only want

> **the next word after the current sentence**

Suppose

Sentence

```text
I love
```

Predictions

```text
After I

↓

love
```

and

```text
After love

↓

Python
```

Which prediction do we need?

Obviously

```text
After love
```

because

"love"

is the last word.

---

That's why this line exists.

```python
logits = logits[:, -1, :]
```

This is probably the hardest line for beginners.

Let's understand it carefully.

---

Suppose

```python
logits.shape

(2,4,65)
```

Meaning

```text
2 sentences

4 tokens

65 vocabulary scores
```

Think of it like

```text
Sentence 1

Token1

Token2

Token3

Token4


Sentence2

Token1

Token2

Token3

Token4
```

Every token has predictions.

---

Now look carefully.

```python
:
```

means

Take **all batches**

---

```python
-1
```

means

Take the **last token**

Python always counts from the end.

Example

```python
a = [5,7,9]
```

Then

```python
a[-1]
```

returns

```text
9
```

Similarly

```python
logits[:, -1, :]
```

means

Take

All batches

↓

Last token

↓

All vocabulary scores

---

Suppose logits originally were

```text
(B,T,C)

(2,4,65)
```

After slicing

```text
(B,C)

(2,65)
```

Now we only have predictions for the last word.

Exactly what we need.

---

# Why Softmax?

Currently

```text
[2.4,8.2,1.7,5.1]
```

These are just scores.

They don't mean probabilities.

Some are negative.

Some are positive.

Some are huge.

---

Softmax converts

```text
[2.4,8.2,1.7,5.1]
```

into

```text
[0.002

0.91

0.001

0.087]
```

Now

Everything

* is between 0 and 1
* sums to 1

Now we have probabilities.

---

Code

```python
probs = F.softmax(logits, dim=-1)
```

Notice

```python
dim=-1
```

means

Apply softmax across

the vocabulary dimension.

Suppose

```text
65 scores
```

become

```text
65 probabilities
```

---

# Choosing the next token

Now comes one of the smartest parts.

```python
idx_next = torch.multinomial(probs, num_samples=1)
```

Let's understand why this isn't simply

```python
argmax()
```

---

Suppose probabilities are

| Token | Probability |
| ----- | ----------- |
| cat   | 0.60        |
| dog   | 0.30        |
| bird  | 0.10        |

If we always choose

```python
argmax
```

The model always says

```text
cat
```

Every single time.

Generated text becomes repetitive.

---

Instead,

PyTorch samples randomly.

Imagine a spinning wheel.

```text
cat

60%
```

```text
dog

30%
```

```text
bird

10%
```

Most of the time

```text
cat
```

Sometimes

```text
dog
```

Rarely

```text
bird
```

This randomness makes generated text much more natural.

---

Suppose

```text
Probabilities

[0.1

0.8

0.1]
```

`torch.multinomial()` might return

```python
tensor([[1]])
```

because token 1 had the highest probability.

Or occasionally

```python
tensor([[2]])
```

because it randomly sampled the lower-probability token.

---

# Appending the token

Suppose currently

```python
idx

[[10,35]]
```

meaning

```text
I love
```

The model predicts

```text
Python
```

whose token ID is

```text
17
```

So

```python
idx_next

[[17]]
```

Now we combine them.

```python
idx = torch.cat((idx, idx_next), dim=1)
```

---

What is `torch.cat()`?

It means

> **concatenate**

Example

```python
a = [1,2]

b = [3]
```

After concatenation

```text
[1,2,3]
```

Same thing here.

Before

```text
I love
```

↓

```python
[[10,35]]
```

New token

```python
[[17]]
```

After concatenation

```python
[[10,35,17]]
```

Sentence becomes

```text
I love Python
```

---

Notice

```python
dim=1
```

means

Join columns

not rows.

So

```text
(1,2)

+

(1,1)

↓

(1,3)
```

The sentence grows longer.

---

# Next iteration

Now the loop repeats.

Current sentence

```text
I love Python
```

Run model again.

Predict

```text
is
```

Append.

Sentence becomes

```text
I love Python is
```

Repeat again.

---

# Final return

After

100 iterations

Suppose

```text
I love
```

became

```text
I love Python because it is a wonderful programming language ...
```

The method returns

```python
idx
```

which now contains **all the token IDs**, including the newly generated ones.

Later, the notebook converts those token IDs back to text using:

```python
decode(idx.tolist())
```

---

# Let's trace one complete example

Suppose our tiny vocabulary is:

```text
0 = I
1 = love
2 = Python
3 = .
```

We start with:

```python
idx = [[0]]
```

which means:

```text
I
```

### Iteration 1

Current input:

```text
I
```

Model predicts probabilities:

```text
love    90%
Python   5%
.        5%
```

Sampled token:

```text
love
```

Now:

```text
I love
```

---

### Iteration 2

Current input:

```text
I love
```

Model predicts:

```text
Python 95%
.        5%
```

Sampled:

```text
Python
```

Now:

```text
I love Python
```

---

### Iteration 3

Current input:

```text
I love Python
```

Model predicts:

```text
. 98%
```

Sampled:

```text
.
```

Final output:

```text
I love Python.
```

---

# The entire `generate()` method in one diagram

```text
Start with input tokens
        │
        ▼
+-------------------------+
| Run forward()           |
+-------------------------+
        │
        ▼
Get logits for every token
        │
        ▼
Keep only the last token's logits
        │
        ▼
Softmax
        │
        ▼
Probability distribution
        │
        ▼
Sample one token
        │
        ▼
Append to input sequence
        │
        ▼
Have we generated enough tokens?
        │
    Yes │ No
        │
        ▼
     Return sequence
```

## One important observation

You might be wondering:

> **If this is a *Bigram* model, why does `generate()` pass the entire sequence (`idx`) instead of just the last token?**

That's an excellent question.

The answer reveals an important design pattern used in all LLMs:

* The **API** always passes the **entire sequence** to the model.
* A **Bigram model** ignores all earlier tokens and effectively uses only the current token (because each token's prediction comes from an independent embedding lookup).
* A **Transformer/GPT model**, which you'll build later in the notebook, uses the **entire sequence** through self-attention.

So the `generate()` code is already written in the same style that GPT uses. Only the implementation of `forward()` changes later—the generation loop stays almost identical. This is one of the reasons Karpathy structures the notebook this way: as the model becomes more powerful, the generation code barely changes.
