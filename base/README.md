# Final Projecct: Dynamic Typing
The goal of this project was to incorporate dynamic typing into our Python based compiler. 
This will help provide increased flexibility of type usage in our language as well as 
allow for more complex type checking. With the addition of dynamic typing, writing code
will be more streamlined and readable when sharing between developers. 

## Approach Taken
The approach we had for the project reflects the outline provided by the in class exercises
and chapter 10 in the book. To start we modified the type system to include the dataclass AnyVal
to allow us to represent any value, regardless of its type.  We then added the inject and project functions 
to convert values between different types. 
The insert_cast function was also added, which allowed us to insert type casts into the code at compile time.
In conjunction with the insert_cast function, we also added the reveal_cast function to allow us to see the correct
type of the dynamically typed value.


## Features Not Implemented
The things we did not get to implement in our dynamic typing implementation is the checking of 
both tuples and functions. We think this is something that could be accomplished with a bit more time,
but currently have not gone through the logic to accomplish them. Given this, our dynamic typing implementation 
will only work with integers, booleans, and strings.
